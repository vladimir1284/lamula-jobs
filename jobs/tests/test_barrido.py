"""La puerta de F2 que no necesita el ORPG: un job cancelado a mitad no deja schema, rol ni objetos."""

from conftest import MIGRACIONES, SECRETS, claves, dia_unico
from lamula_jobs import queue, service, sweep, tenancy


def test_cancelado_a_mitad_no_deja_nada_y_el_vecino_sigue_intacto(api_conn, runner_conn, admin, token, almacen):
    tok = queue.validar_token(admin, token["token"])
    base = sweep.huerfanos(admin)  # los roles son del clúster: puede haber ajenos (otras bases del mismo Postgres)
    mk = lambda icao: service.crear_job(api_conn, tok, icao=icao, secrets=SECRETS, migraciones=MIGRACIONES,
                                        entradas=[queue.Entrada(k, 5) for k in claves(icao, dia_unico(), 2)])
    a, b = mk("KAMX"), mk("KHGX")
    admin.execute("UPDATE control.jobs SET state='cancelled' WHERE state='queued' AND id NOT IN (%s,%s)", (a["id"], b["id"]))
    for j in (a, b):
        for e in queue.entradas_de(admin, j["id"]):
            almacen.s3.put_object(Bucket="staging", Key=e["staging_key"], Body=b"vol")
    # A está a mitad: tiene una fila y un COG publicados
    got = queue.tomar(runner_conn, "r1")
    assert got["id"] == a["id"]
    queue.empezar(runner_conn, a["id"], "r1")
    for jid, key in ((a["id"], "AMX/N0B/a.tif"), (b["id"], "HGX/N0B/b.tif")):
        S = tenancy.schema_de(jid)
        admin.execute(f"INSERT INTO {S}.radars VALUES ('{key[:3]}','K{key[:3]}',1,1,1,'p','a','b')")
        admin.execute(f"INSERT INTO {S}.products VALUES (153,'N0B','dBZ','raster')")
        admin.execute(f"""INSERT INTO {S}.rasters (site_id,product_code,vol_time,r2_key,size_bytes,value_scale,value_offset,width,height,cell_m,created_at)
                          VALUES ('{key[:3]}',153,'t','{key}',1,1,0,1,1,1,'t')""")
        almacen.s3.put_object(Bucket="cogs", Key=key, Body=b"cog")
    assert queue.cancelar(api_conn, a["id"]) == "cancel_requested"
    assert queue.latir(runner_conn, a["id"], "r1") is True
    queue.terminar(runner_conn, a["id"], "r1", cancelado=True)
    sweep.barrer(api_conn, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)
    # A: nada de nada
    assert admin.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (tenancy.schema_de(a["id"]),)).fetchone() is None
    assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname LIKE %s", (f"job\\_{a['id']}%",)).fetchone() is None
    keys = {o["Key"] for o in almacen.s3.list_objects_v2(Bucket="cogs").get("Contents", [])}
    assert keys == {"HGX/N0B/b.tif"}
    assert {o["Key"] for o in almacen.s3.list_objects_v2(Bucket="staging").get("Contents", [])} == {e["staging_key"] for e in queue.entradas_de(admin, b["id"])}
    # B: intacto, con su fila
    assert admin.execute(f"SELECT count(*) AS n FROM {tenancy.schema_de(b['id'])}.rasters").fetchone()["n"] == 1
    assert not [h for h in sweep.huerfanos(admin)["schemas"] if a["id"] in h]
    queue.cancelar(api_conn, b["id"])
    sweep.barrer(api_conn, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)
    assert sweep.huerfanos(admin) == base


def test_barrido_es_idempotente_y_caduca(api_conn, admin, token, almacen):
    tok = queue.validar_token(admin, token["token"])
    j = service.crear_job(api_conn, tok, icao="KAMX", secrets=SECRETS, migraciones=MIGRACIONES,
                          entradas=[queue.Entrada(k) for k in claves("KAMX", dia_unico(), 1)])
    admin.execute("UPDATE control.jobs SET state='ready', expires_at = now() - interval '1 s' WHERE id=%s", (j["id"],))
    r1 = sweep.barrer(api_conn, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)
    r2 = sweep.barrer(api_conn, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)
    assert j["id"] in r1["dropped"] and r2["dropped"] == []
    assert queue.obtener(admin, j["id"])["state"] == "expired"


def test_alta_incompleta_no_deja_job_ni_schema(api_conn, admin, token, tmp_path):
    tok = queue.validar_token(admin, token["token"])
    mala = tmp_path / "m"
    mala.mkdir()
    (mala / "0001.sql").write_text("SELECT * FROM no_existe;")
    import pytest, psycopg
    antes = admin.execute("SELECT count(*) AS n FROM control.jobs").fetchone()["n"]
    base = sweep.huerfanos(admin)
    with pytest.raises(psycopg.errors.UndefinedTable):
        service.crear_job(api_conn, tok, icao="KAMX", secrets=SECRETS, migraciones=mala,
                          entradas=[queue.Entrada(k) for k in claves("KAMX", dia_unico(), 1)])
    assert admin.execute("SELECT count(*) AS n FROM control.jobs").fetchone()["n"] == antes
    assert sweep.huerfanos(admin) == base


def test_salud_avisa_de_cola_sin_worker_y_de_latido_viejo(api_conn, admin, token):
    tok = queue.validar_token(admin, token["token"])
    j = service.crear_job(api_conn, tok, icao="KAMX", secrets=SECRETS, migraciones=MIGRACIONES,
                          entradas=[queue.Entrada(k) for k in claves("KAMX", dia_unico(), 1)])
    mio = lambda h: [x["id"] for x in h if x["id"] == j["id"]]
    s = sweep.salud(admin)
    assert not mio(s["sin_reclamar"]) and not mio(s["latido_viejo"])          # recién en cola: sano
    admin.execute("UPDATE control.jobs SET created_at = now() - interval '10 minutes' WHERE id=%s", (j["id"],))
    assert mio(sweep.salud(admin)["sin_reclamar"])                             # nadie lo toma: alarma
    assert not mio(sweep.salud(admin, cola_max_s=3600)["sin_reclamar"])        # el umbral se respeta
    admin.execute("UPDATE control.jobs SET state='ingesting', claimed_by='r', heartbeat_at = now() - interval '10 minutes' WHERE id=%s", (j["id"],))
    s = sweep.salud(admin)
    assert mio(s["latido_viejo"]) and not mio(s["sin_reclamar"])               # reclamado y callado: otra alarma
    admin.execute("UPDATE control.jobs SET state='cancelled' WHERE id=%s", (j["id"],))
    s = sweep.salud(admin)
    assert not mio(s["latido_viejo"]) and not mio(s["sin_reclamar"])           # terminado: no cuenta


def test_expire_libera_el_radar_y_no_toca_lo_que_corre(api_conn, admin, token, almacen):
    import pytest
    tok = queue.validar_token(admin, token["token"])
    dia = dia_unico()
    mk = lambda: service.crear_job(api_conn, tok, icao="KAMX", secrets=SECRETS, migraciones=MIGRACIONES,
                                   entradas=[queue.Entrada(k, 5) for k in claves("KAMX", dia, 1)])
    base = sweep.huerfanos(admin)
    j = mk()
    for e in queue.entradas_de(admin, j["id"]):
        almacen.s3.put_object(Bucket="staging", Key=e["staging_key"], Body=b"vol")
    # en cola: no se caduca, y no se borra nada
    assert sweep.caducar(api_conn, almacen, j["id"]) == {"state": "queued", "caducado": False}
    assert queue.obtener(admin, j["id"])["state"] == "queued"
    # ready: caduca, borra todo y deja libre el radar y las horas (D14)
    admin.execute("UPDATE control.jobs SET state='ready' WHERE id=%s", (j["id"],))
    r = sweep.caducar(api_conn, almacen, j["id"])
    assert r["caducado"] and r["state"] == "expired"
    assert queue.obtener(admin, j["id"])["state"] == "expired"
    assert admin.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (tenancy.schema_de(j["id"]),)).fetchone() is None
    assert not {o["Key"] for o in almacen.s3.list_objects_v2(Bucket="staging").get("Contents", [])} & {e["staging_key"] for e in queue.entradas_de(admin, j["id"])}
    assert sweep.huerfanos(admin) == base
    otro = mk()                                                                # antes habría dado Solapado
    # repetir no rompe nada
    assert sweep.caducar(api_conn, almacen, j["id"]) == {"state": "expired", "caducado": False}
    with pytest.raises(KeyError):
        sweep.caducar(api_conn, almacen, "no-existe")
    queue.cancelar(api_conn, otro["id"])
    sweep.barrer(api_conn, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)
    assert sweep.huerfanos(admin) == base


def test_barrido_reclama_a_los_120_s_y_no_antes(api_conn, admin, token, almacen):
    tok = queue.validar_token(admin, token["token"])
    j = service.crear_job(api_conn, tok, icao="KAMX", secrets=SECRETS, migraciones=MIGRACIONES,
                          entradas=[queue.Entrada(k) for k in claves("KAMX", dia_unico(), 1)])
    assert sweep.TIMEOUT_MUERTO_S == 120 and sweep.LATIDO_AVISO_S < sweep.TIMEOUT_MUERTO_S
    ve = lambda: queue.obtener(admin, j["id"])["state"]
    admin.execute("UPDATE control.jobs SET state='ingesting', claimed_by='r', attempts=1, heartbeat_at = now() - interval '100 s' WHERE id=%s", (j["id"],))
    sweep.barrer(api_conn, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)
    assert ve() == "ingesting"                                                 # 100 s: aún dentro del timeout
    assert [x for x in sweep.salud(admin)["latido_viejo"] if x["id"] == j["id"]]  # pero `health` ya avisa
    admin.execute("UPDATE control.jobs SET heartbeat_at = now() - interval '130 s' WHERE id=%s", (j["id"],))
    r = sweep.barrer(api_conn, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)
    assert j["id"] in r["requeued"] and ve() == "queued"
    queue.cancelar(api_conn, j["id"])
    sweep.barrer(api_conn, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)
