"""Puerta de publicación durante el job (requisito de F3): los productos aparecen *mientras* el ORPG reproduce.

    PYTHONPATH=e2e uv run python -u e2e/vivo.py <fichero-con-el-token> <dir-con-volumenes> [N] [salida.json]

Sube los N primeros volúmenes de KAMX (por defecto 3), crea el job y muestrea cada 5 s el estado y el número
de filas de `rasters` en el schema del job. Lo que comprueba:

- la primera fila aparece con el job todavía en `ingesting` (no al final);
- el número de filas crece en al menos dos pasos distintos antes de `ready`;
- el job acaba `ready`, con el número final de filas igual al del último muestreo vivo o mayor.

Guarda la serie `(t, estado, rasters)` y el instante del primer producto: es la cifra que importa al viewer
(cuánto hay que esperar para ver algo). Supone `prepare.py`, la API, moto y el contenedor `job-f2` arriba.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import lib
from lamula_jobs import tenancy

TOK = open(sys.argv[1]).read().strip()
N = int(sys.argv[3]) if len(sys.argv) > 3 else 3
VOLS = sorted(p for p in Path(sys.argv[2]).iterdir() if p.name.startswith("KAMX") and p.name.endswith("_V06"))[:N]
SALIDA = Path(sys.argv[4]) if len(sys.argv) > 4 else Path("vivo.json")


def main() -> int:
    db = lib.admin_db()
    if not lib.worker_vivo():
        subprocess.run(["docker", "exec", "-d", lib.CONTENEDOR, "bash", "-lc",
                        "jobs-supervisor --metricas /data/wear-vivo.jsonl >> /data/supervisor-vivo.log 2>&1"], check=True)
        time.sleep(5)
    antes = lib.huerfanos()
    j = lib.alta(TOK, "KAMX", [lib.subir(str(v)) for v in VOLS])
    sch = tenancy.schema_de(j["id"])
    print(f"[{time.strftime('%H:%M:%S')}] job {j['id']}: {len(VOLS)} volúmenes", flush=True)
    serie, t0, ultimo = [], time.monotonic(), (None, None)
    while True:
        est = db.execute("SELECT state FROM control.jobs WHERE id=%s", (j["id"],)).fetchone()["state"]
        n = db.execute(f"SELECT count(*) AS n FROM {sch}.rasters").fetchone()["n"] if db.execute(
            "SELECT 1 FROM pg_namespace WHERE nspname=%s", (sch,)).fetchone() else 0
        t = time.monotonic() - t0
        serie.append((round(t, 1), est, n))
        if (est, n) != ultimo:
            print(f"[{time.strftime('%H:%M:%S')}] +{t:.0f}s {est} rasters={n}", flush=True)
            ultimo = (est, n)
        if est in ("ready", "failed", "cancelled"):
            break
        if t > 3 * 3600:
            print("ABORTO: más de 3 h", flush=True)
            break
        time.sleep(5)

    vivos = [(t, e, n) for t, e, n in serie if e == "ingesting"]
    primero = next((t for t, e, n in vivos if n > 0), None)
    pasos = len({n for _, _, n in vivos if n > 0})
    fin = serie[-1]
    fila = db.execute("SELECT state, error FROM control.jobs WHERE id=%s", (j["id"],)).fetchone()
    ingesting_desde = next((t for t, e, _ in serie if e == "ingesting"), None)
    res = {"job": j["id"], "volumenes": len(VOLS), "estado": dict(fila), "duracion_s": round(fin[0]),
           "ingesting_desde_s": ingesting_desde, "primer_producto_s": primero,
           "espera_hasta_primer_producto_s": None if primero is None else round(primero - ingesting_desde, 1),
           "pasos_distintos_con_job_vivo": pasos, "rasters_al_ultimo_muestreo_vivo": vivos[-1][2] if vivos else None,
           "rasters_finales": fin[2], "huerfanos_antes": antes, "huerfanos_despues": lib.huerfanos(), "serie": serie}
    SALIDA.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: v for k, v in res.items() if k != "serie"}, indent=1, default=str))
    ok = fila["state"] == "ready" and primero is not None and pasos >= 2 and res["huerfanos_despues"] == antes
    print("PUBLICACIÓN DURANTE EL JOB:", "OK" if ok else "FALLA")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
