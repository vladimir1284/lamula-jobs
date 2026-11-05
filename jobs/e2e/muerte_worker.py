"""Prueba de F2 con el ORPG de verdad: el worker muere (kill -9) a mitad de reproducción.

    . loadenv.sh f2.env && uv run python e2e/muerte_worker.py <fichero-con-el-token>

Supone `prepare.py` hecho, la API en :58000, moto en :55000 y el contenedor `job-f2` arriba con la imagen
que trae `jobs-supervisor`. El worker se lanza con el supervisor, no suelto.

Qué demuestra, en orden:
  1. El supervisor relanza al worker muerto en segundos.
  2. El job queda reclamado por el worker muerto; el barrido (con un timeout corto, aquí 40 s) lo
     devuelve a la cola con el schema nuevo y vacío.
  3. El worker nuevo lo reclama (intento 2), limpia el ORPG que dejó huérfano el muerto y lo termina `ready`.
  4. No quedan procesos del ORPG de más, ni schemas ni roles huérfanos.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import lib

TOK = open(sys.argv[1]).read().strip()
VOLUMEN = "/home/vladimir/Documents/Trabajo/Nitza/lamula-jobs/f0-run/ar2in12/KAMX20170910_170248_V06"
TIMEOUT_MUERTO = 40  # s sin latido; en producción son 600


def paso(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def pid_worker() -> list[int]:
    return [int(x) for x in lib.en_contenedor("bash", "-c", "pgrep -f '[l]amula_jobs.worker'").stdout.split()]


def barrer(timeout_s: int) -> dict:
    from lamula_jobs import sweep
    import os
    with lib.admin_db() as c:
        return sweep.barrer(c, lib._almacen(), migraciones=Path(os.environ["PIPELINE_MIGRATIONS"]),
                            rw=os.environ["JOBS_RW_SECRET"].encode(), ro=os.environ["JOBS_RO_SECRET"].encode(), timeout_s=timeout_s)


def main() -> int:
    db = lib.admin_db()
    if not pid_worker():
        import subprocess
        subprocess.run(["docker", "exec", "-d", lib.CONTENEDOR, "bash", "-lc",
                        "jobs-supervisor >> /data/supervisor-f2.log 2>&1"], check=True)
        time.sleep(5)
    viejo = pid_worker()
    assert len(viejo) == 1, f"debería haber un worker, hay {viejo}"
    antes = lib.huerfanos()
    paso(f"worker {viejo}; huérfanos al empezar: {antes}")

    j = lib.alta(TOK, "KAMX", [lib.subir(VOLUMEN)])
    paso(f"job {j['id']}")
    lib.esperar(db, j["id"], {"ingesting"}, 300)
    fin = time.monotonic() + 300
    while lib.procesos("play_a2") == 0 and time.monotonic() < fin:
        time.sleep(3)
    assert lib.procesos("play_a2") == 1, "play_a2 no arrancó"
    time.sleep(20)

    lib.en_contenedor("kill", "-9", str(viejo[0]))
    t0 = time.monotonic()
    paso(f"worker {viejo[0]} muerto con kill -9, con play_a2 en marcha")

    # 1. el supervisor lo relanza
    while True:
        nuevo = pid_worker()
        if nuevo and nuevo != viejo:
            break
        assert time.monotonic() - t0 < 60, "el supervisor no relanzó el worker en 60 s"
        time.sleep(1)
    paso(f"1. supervisor: worker nuevo {nuevo} a los {time.monotonic() - t0:.0f} s")
    estado = db.execute("SELECT state, claimed_by, attempts FROM control.jobs WHERE id=%s", (j["id"],)).fetchone()
    paso(f"   el job sigue así (lo tiene el muerto, aún dentro del timeout): {dict(estado)}")
    assert estado["state"] in ("claimed", "ingesting"), estado

    # 2. el barrido lo devuelve a la cola
    time.sleep(max(0, TIMEOUT_MUERTO + 5 - (time.monotonic() - t0)))
    r = barrer(TIMEOUT_MUERTO)
    paso(f"2. barrido: {r}")
    assert j["id"] in r["requeued"], r

    # 3. el worker nuevo lo termina
    est = lib.esperar(db, j["id"], {"ready", "failed", "cancelled"}, 900, cada=5)
    fila = db.execute("SELECT state, attempts, error FROM control.jobs WHERE id=%s", (j["id"],)).fetchone()
    paso(f"3. estado final: {dict(fila)}")
    assert est == "ready" and fila["attempts"] == 2, fila

    # 4. sin restos
    time.sleep(5)
    vivos = {n: lib.procesos(n) for n in ("play_a2", "nbtcp")}
    paso(f"4. procesos del ORPG tras terminar: {vivos}; workers: {pid_worker()}")
    assert not any(vivos.values()), vivos
    assert len(pid_worker()) == 1
    paso(f"   barrido final: {lib.barrer()}")
    assert lib.huerfanos() == antes, lib.huerfanos()
    paso("MUERTE DEL WORKER OK: relanzado, job reintentado y terminado, sin restos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
