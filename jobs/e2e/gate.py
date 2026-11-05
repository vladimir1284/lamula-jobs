"""Puerta de F2 con el ORPG de verdad: cancelación a mitad y dos jobs seguidos de sitios distintos.

    . loadenv.sh f2.env && uv run python e2e/gate.py <fichero-con-el-token> [--volumenes-staging ...]

Supone `prepare.py` hecho, la API en :58000, moto en :55000 y el contenedor `job-f2` arriba.
"""

from __future__ import annotations

import sys
import time

import lib

TOK = open(sys.argv[1]).read().strip()
F0 = "/home/vladimir/Documents/Trabajo/Nitza/lamula-jobs/f0-run"
KAMX_A = F0 + "/ar2in12/KAMX20170910_170248_V06"
KHGX = F0 + "/ar2in-khgx/KHGX20261101_162110_V06"


def paso(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    db = lib.admin_db()
    lib.lanzar_worker()
    antes = lib.huerfanos()
    paso(f"huérfanos al empezar: {antes}")

    # ---- 1. cancelación a mitad, con el ORPG reproduciendo
    c = lib.alta(TOK, "KAMX", [lib.subir(KAMX_A)])
    paso(f"job de cancelación {c['id']}")
    lib.esperar(db, c["id"], {"ingesting"}, 300)
    fin = time.monotonic() + 300
    while lib.procesos("play_a2") == 0 and time.monotonic() < fin:
        time.sleep(3)
    assert lib.procesos("play_a2") == 1, "play_a2 no arrancó"
    time.sleep(20)  # que haya productos en vuelo
    code, r = lib.api("POST", f"/v1/jobs/{c['id']}/cancel", TOK)
    paso(f"cancelación pedida: {code} {r}")
    t0 = time.monotonic()
    est = lib.esperar(db, c["id"], {"cancelled", "failed", "ready"}, 400, cada=2)
    paso(f"estado {est} {time.monotonic() - t0:.0f} s después de cancelar")
    assert est == "cancelled", est
    time.sleep(3)
    vivos = {n: lib.procesos(n) for n in ("play_a2", "nbtcp", "mrpg")}
    paso(f"procesos del ORPG tras cancelar: {vivos}")
    assert not any(vivos.values()), vivos
    assert lib.en_contenedor("bash", "-c", f"ls /data/jobs/{c['id']} 2>&1").returncode != 0, "el directorio de trabajo sigue ahí"
    paso(f"barrido: {lib.barrer()}")
    from lamula_jobs import tenancy
    sch = tenancy.schema_de(c["id"])
    assert db.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (sch,)).fetchone() is None, "schema huérfano"
    assert db.execute("SELECT 1 FROM pg_roles WHERE rolname LIKE %s", (f"job\\_{c['id']}%",)).fetchone() is None, "rol huérfano"
    assert lib.huerfanos() == antes, lib.huerfanos()
    paso("CANCELACIÓN OK: sin schema, sin rol, sin procesos, sin directorio")

    # ---- 2. dos jobs seguidos, sitios distintos, lanzados a la vez por la API
    a = lib.alta(TOK, "KAMX", [lib.subir(KAMX_A)])
    b = lib.alta(TOK, "KHGX", [lib.subir(KHGX)])
    paso(f"jobs {a['id']} (KAMX) y {b['id']} (KHGX)")
    for j in (a, b):
        est = lib.esperar(db, j["id"], {"ready", "failed", "cancelled"}, 1800, cada=10)
        paso(f"{j['icao']}: {est}")
        assert est == "ready", db.execute("SELECT error FROM control.jobs WHERE id=%s", (j["id"],)).fetchone()
    for j, site, lat, lon in ((a, "AMX", 25.611, -80.413), (b, "HGX", None, None)):
        S = tenancy.schema_de(j["id"])
        radars = db.execute(f"SELECT site_id, lat, lon, last_seen_at FROM {S}.radars").fetchall()
        sites = {r["site_id"] for r in db.execute(f"SELECT DISTINCT site_id FROM {S}.rasters")}
        n = db.execute(f"SELECT count(*) AS n FROM {S}.rasters").fetchone()["n"]
        paso(f"{S}: radars={radars} sites_en_rasters={sites} rasters={n}")
        assert [r["site_id"] for r in radars] == [site] and sites == {site} and n > 0
        if lat:
            assert abs(radars[0]["lat"] - lat) < 0.001 and abs(radars[0]["lon"] - lon) < 0.001
    ks = lib.claves("lamula-demo-raster")
    paso(f"objetos en el bucket: {len(ks)}; prefijos {sorted({k.split('/')[0] for k in ks})}")
    assert {k.split("/")[0] for k in ks} == {"AMX", "HGX"}
    paso("DOS JOBS OK: cada schema solo tiene su sitio y los objetos están donde toca")
    print("GATE F2 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
