"""Tanda de desgaste de F2: N jobs de un volumen, seguidos, alternando KAMX y KHGX, detrás de la cola.

Tras cada job comprueba coordenadas y que el schema solo tenga su sitio, anota la foto de procesos y
memoria que toma el worker, y caduca el job y barre (así también se ejercita 12 veces el borrado de
schemas, roles y objetos). Al final exige: cero huérfanos, bucket vacío, ningún proceso del ORPG vivo.

    . loadenv.sh f2.env && PYTHONPATH=e2e uv run python e2e/desgaste.py <token> [N] > desgaste.log
"""

from __future__ import annotations

import json
import sys
import time

import lib
from lamula_jobs import tenancy

TOK = open(sys.argv[1]).read().strip()
N = int(sys.argv[2]) if len(sys.argv) > 2 else 12
F0 = "/home/vladimir/Documents/Trabajo/Nitza/lamula-jobs/f0-run"
import glob
KAMX = sorted(glob.glob(f"{F0}/ar2in12/KAMX*_V06"))[:6]
KHGX = [f"{F0}/ar2in-khgx/KHGX20261101_{h}_V06" for h in ("162110", "162815")]
ESPERADO = {"AMX": (25.611, -80.413)}  # HGX se lee de change_radar.dat del contenedor


def p(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def metricas_de(job_id: str) -> dict | None:
    for ln in lib.en_contenedor("cat", "/data/wear-f2.jsonl").stdout.splitlines():
        m = json.loads(ln)
        if m["job"] == job_id:
            return m
    return None


def main() -> int:
    assert len(KAMX) == 6 and all(glob.glob(f) for f in KHGX)
    hgx = lib.en_contenedor("bash", "-lc", "grep -i '^khgx' ~/tools/cfg/change_radar.dat").stdout.split(",")
    ESPERADO["HGX"] = (int(hgx[1]) / 1000, int(hgx[2]) / 1000)
    db = lib.admin_db()
    lib.lanzar_worker()
    filas = []
    for i in range(N):
        icao = "KAMX" if i % 2 == 0 else "KHGX"
        site = icao[1:]
        vol = (KAMX if icao == "KAMX" else KHGX)[(i // 2) % (6 if icao == "KAMX" else 2)]
        j = lib.alta(TOK, icao, [lib.subir(vol)])
        t0 = time.monotonic()
        est = lib.esperar(db, j["id"], {"ready", "failed", "cancelled"}, 1800, cada=5)
        dur = time.monotonic() - t0
        S = tenancy.schema_de(j["id"])
        fila = {"i": i + 1, "icao": icao, "estado": est, "s": round(dur)}
        if est == "ready":
            rd = db.execute(f"SELECT site_id, lat, lon FROM {S}.radars").fetchall()
            sites = {r["site_id"] for r in db.execute(f"SELECT DISTINCT site_id FROM {S}.rasters")}
            fila["rasters"] = db.execute(f"SELECT count(*) AS n FROM {S}.rasters").fetchone()["n"]
            la, lo = ESPERADO[site]
            fila["coords_ok"] = len(rd) == 1 and rd[0]["site_id"] == site and abs(rd[0]["lat"] - la) < 0.001 and abs(rd[0]["lon"] - lo) < 0.001 and sites == {site}
        else:
            fila["error"] = db.execute("SELECT error FROM control.jobs WHERE id=%s", (j["id"],)).fetchone()["error"]
        time.sleep(3)
        m = metricas_de(j["id"])
        if m:
            fila.update(procs=m["procs"], rss_mib=round(m["rss_kib"] / 1024), mrpg_kib=m["mrpg_kib"], owr_server_kib=m["owr_server_kib"], top=m["top_kib"])
        fila["play_a2/nbtcp/mrpg"] = [lib.procesos(n) for n in ("play_a2", "nbtcp", "mrpg")]
        db.execute("UPDATE control.jobs SET expires_at = now() - interval '1 s' WHERE id=%s AND state IN ('ready','failed')", (j["id"],))
        lib.barrer()
        filas.append(fila)
        p(json.dumps(fila, ensure_ascii=False))
    ok = all(f["estado"] == "ready" and f.get("coords_ok") for f in filas)
    h = lib.huerfanos()
    cub = lib.claves("lamula-demo-raster")
    p(f"huérfanos: {h}; objetos en el bucket: {len(cub)}")
    assert ok and h == {"schemas": [], "roles": []} and not cub, "la tanda NO pasa"
    p("TANDA DE DESGASTE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
