"""Mide el margen del timeout de runner muerto (600 s) con un job largo de verdad por la cola.

    . loadenv; uv run python e2e/timeout_runner.py <fichero-con-el-token> <dir-con-volumenes> [salida.json]

El barrido declara muerto a un job cuyo latido tiene más de `timeout_s` (600 en producción). El worker late cada
10 s desde un hilo. Lo que no se sabía: si ese hilo aguanta una hora y pico con el ORPG a pleno (125 % de CPU de
pico) sin dejar huecos largos. Aquí se muestrea `now() - heartbeat_at` (reloj de la base) cada 2 s durante todo
el job y se guarda el máximo, los percentiles y los huecos > 30 s. También compara la duración real del paso
del runner con el tope del worker (n*12*60+1800 s).

Supone `prepare.py`, la API, moto y el contenedor `job-f2` arriba. Lanza el worker con el supervisor.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import lib

TOK = open(sys.argv[1]).read().strip()
VOLS = sorted(p for p in Path(sys.argv[2]).iterdir() if p.name.startswith("KAMX") and p.name.endswith("_V06"))
SALIDA = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("timeout_runner.json")
MUESTREO_S = 2


def main() -> int:
    db = lib.admin_db()
    if not lib.worker_vivo():
        subprocess.run(["docker", "exec", "-d", lib.CONTENEDOR, "bash", "-lc",
                        "jobs-supervisor --metricas /data/wear-timeout.jsonl >> /data/supervisor-timeout.log 2>&1"], check=True)
        time.sleep(5)
    antes = lib.huerfanos()
    entradas = [lib.subir(str(v)) for v in VOLS]
    j = lib.alta(TOK, "KAMX", entradas)
    print(f"[{time.strftime('%H:%M:%S')}] job {j['id']}: {len(VOLS)} volúmenes", flush=True)

    muestras, estados, t0 = [], [], time.monotonic()
    ultimo = None
    while True:
        r = db.execute("SELECT state, attempts, extract(epoch FROM now() - heartbeat_at) AS gap FROM control.jobs WHERE id=%s", (j["id"],)).fetchone()
        t = time.monotonic() - t0
        if r["state"] != ultimo:
            estados.append((round(t), r["state"]))
            print(f"[{time.strftime('%H:%M:%S')}] +{t:.0f}s {r['state']} (intento {r['attempts']})", flush=True)
            ultimo = r["state"]
        if r["state"] in ("claimed", "ingesting") and r["gap"] is not None:
            muestras.append((round(t, 1), float(r["gap"])))
        if r["state"] in ("ready", "failed", "cancelled"):
            break
        if t > 4 * 3600:
            print("ABORTO: más de 4 h", flush=True)
            break
        time.sleep(MUESTREO_S)

    gaps = sorted(g for _, g in muestras)
    q = lambda p: gaps[min(len(gaps) - 1, int(p * len(gaps)))] if gaps else None  # noqa: E731
    largos = [(t, g) for t, g in muestras if g > 30]
    fila = db.execute("SELECT state, attempts, error FROM control.jobs WHERE id=%s", (j["id"],)).fetchone()
    res = {"job": j["id"], "volumenes": len(VOLS), "estado": dict(fila), "estados": estados, "duracion_s": round(time.monotonic() - t0),
           "muestras": len(gaps), "gap_max_s": gaps[-1] if gaps else None, "gap_p50": q(.5), "gap_p99": q(.99),
           "huecos_mayores_30s": largos[:50], "timeout_barrido_s": 600,  # el de la corrida del 2026-11-05; hoy es sweep.TIMEOUT_MUERTO_S (120, D16) "tope_runner_s": len(VOLS) * 12 * 60 + 1800,
           "huerfanos_antes": antes, "huerfanos_despues": lib.huerfanos()}
    SALIDA.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: v for k, v in res.items() if k != "huecos_mayores_30s"}, indent=1, default=str))
    print(f"huecos > 30 s: {len(largos)}")
    return 0 if fila["state"] == "ready" else 1


if __name__ == "__main__":
    sys.exit(main())
