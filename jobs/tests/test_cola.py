import threading
from datetime import datetime, timezone

import pytest

from conftest import MIGRACIONES, SECRETS, claves, dia_unico
from lamula_jobs import queue, service, sweep, tenancy
from lamula_jobs.ids import ulid


def alta(api_conn, tok, icao="KAMX", dia=None, n=2, minuto0=0):
    dia = dia or dia_unico()
    ents = [queue.Entrada(k, 1000) for k in claves(icao, dia, n, minuto0=minuto0)]
    return service.crear_job(api_conn, tok, icao=icao, entradas=ents, secrets=SECRETS, migraciones=MIGRACIONES)


def limpiar(api_conn, almacen, *ids):
    for i in ids:
        api_conn.execute("UPDATE control.jobs SET state='cancelled' WHERE id=%s", (i,))
    sweep.barrer(api_conn, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)


def test_alta_deja_job_en_cola_con_schema(api_conn, admin, token, almacen):
    tok = queue.validar_token(admin, token["token"])
    j = alta(api_conn, tok)
    assert j["state"] == "queued" and j["n_volumes"] == 2 and j["attempts"] == 0
    assert admin.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (tenancy.schema_de(j["id"]),)).fetchone()
    limpiar(api_conn, almacen, j["id"])


def test_token_revocado_o_caducado_no_valida(admin, token):
    assert queue.validar_token(admin, token["token"])
    admin.execute("UPDATE control.access_tokens SET revoked_at=now() WHERE id=%s", (token["id"],))
    assert queue.validar_token(admin, token["token"]) is None
    admin.execute("UPDATE control.access_tokens SET revoked_at=NULL, expires_at=now()-interval '1 s' WHERE id=%s", (token["id"],))
    assert queue.validar_token(admin, token["token"]) is None
    assert queue.validar_token(admin, "lma_inventado") is None


@pytest.mark.parametrize("token", ["demo"], indirect=True)
def test_cuotas_del_nivel_demo(api_conn, admin, token, almacen):
    tok = queue.validar_token(admin, token["token"])
    with pytest.raises(queue.CuotaExcedida, match="volúmenes"):
        alta(api_conn, tok, n=13)
    a = alta(api_conn, tok, n=2)
    with pytest.raises(queue.CuotaExcedida, match="activo"):  # demo: 1 activo
        alta(api_conn, tok, icao="KHGX", n=2)
    limpiar(api_conn, almacen, a["id"])
    # cancelar libera la plaza activa y NO gasta cuota total (demo: 2 en total)
    b = alta(api_conn, tok, icao="KHGX", n=2)
    c_ = queue.cancelar(api_conn, b["id"])
    assert c_ == "cancelled"
    d = alta(api_conn, tok, icao="KEVX", n=2)
    assert d["state"] == "queued"
    limpiar(api_conn, almacen, b["id"], d["id"])


def test_altas_simultaneas_del_mismo_token_respetan_la_cuota(api_conn, admin, basedatos, almacen):
    """Dos hilos, un token de nivel demo (1 activo): solo uno entra."""
    from conftest import dsn
    import psycopg
    from psycopg.rows import dict_row
    from lamula_jobs.admin import emitir
    tid, t = emitir(admin, email="carrera@test", tier="demo")
    tok = queue.validar_token(admin, t)
    res, errs = [], []

    def hilo(icao):
        with psycopg.connect(dsn(basedatos, "jobs_api", "api-pw"), autocommit=True, row_factory=dict_row) as c:
            try:
                res.append(alta(c, tok, icao=icao, n=1))
            except queue.CuotaExcedida as e:
                errs.append(e)

    ts = [threading.Thread(target=hilo, args=(i,)) for i in ("KAMX", "KHGX")]
    [t_.start() for t_ in ts]
    [t_.join() for t_ in ts]
    assert len(res) == 1 and len(errs) == 1
    limpiar(api_conn, almacen, res[0]["id"])


def test_entradas_invalidas(api_conn, admin, token):
    tok = queue.validar_token(admin, token["token"])
    ks = claves("KAMX", "20170905", 2)
    with pytest.raises(queue.EntradaInvalida, match="orden"):
        service.crear_job(api_conn, tok, icao="KAMX", entradas=[queue.Entrada(ks[1]), queue.Entrada(ks[0])], secrets=SECRETS, migraciones=MIGRACIONES)
    with pytest.raises(queue.EntradaInvalida, match="no es un volumen de KHGX"):
        service.crear_job(api_conn, tok, icao="KHGX", entradas=[queue.Entrada(ks[0])], secrets=SECRETS, migraciones=MIGRACIONES)
    with pytest.raises(queue.EntradaInvalida):
        service.crear_job(api_conn, tok, icao="KAMX", entradas=[], secrets=SECRETS, migraciones=MIGRACIONES)
    with pytest.raises(queue.EntradaInvalida):
        service.crear_job(api_conn, tok, icao="kamx; --", entradas=[queue.Entrada(ks[0])], secrets=SECRETS, migraciones=MIGRACIONES)


@pytest.mark.parametrize("token", ["amplio"], indirect=True)
def test_solapado_mismo_radar_se_rechaza_y_distinto_radar_o_distinta_hora_no(api_conn, admin, token, almacen):
    tok = queue.validar_token(admin, token["token"])
    D = dia_unico()
    a = alta(api_conn, tok, "KAMX", D, 3, minuto0=0)         # 00:00-00:10
    with pytest.raises(queue.Solapado):
        alta(api_conn, tok, "KAMX", D, 2, minuto0=5)          # 00:05-00:10
    b = alta(api_conn, tok, "KHGX", D, 3, minuto0=0)          # otro radar, mismas horas
    c = alta(api_conn, tok, "KAMX", D, 2, minuto0=120)        # mismo radar, otras horas
    limpiar(api_conn, almacen, a["id"], b["id"], c["id"])
    d = alta(api_conn, tok, "KAMX", D, 3, minuto0=0)          # el cancelado ya no bloquea
    limpiar(api_conn, almacen, d["id"])


@pytest.mark.parametrize("token", ["amplio"], indirect=True)
def test_tomar_es_exclusivo_y_respeta_prioridad_y_antiguedad(api_conn, runner_conn, admin, token, almacen, basedatos):
    tok = queue.validar_token(admin, token["token"])
    ids = [alta(api_conn, tok, "KAMX", dia_unico(), 1)["id"] for i in range(2)]
    admin.execute("UPDATE control.jobs SET priority = 5 WHERE id = %s", (ids[1],))
    # nada en la cola salvo los nuestros: vaciamos los demás para que el orden sea el de este test
    admin.execute("UPDATE control.jobs SET state='cancelled' WHERE state='queued' AND id <> ALL(%s)", (ids,))
    r1 = queue.tomar(runner_conn, "r1")
    r2 = queue.tomar(runner_conn, "r2")
    assert (r1["id"], r2["id"]) == (ids[1], ids[0])  # prioridad primero
    assert queue.tomar(runner_conn, "r3") is None
    limpiar(api_conn, almacen, *ids)


@pytest.mark.parametrize("token", ["amplio"], indirect=True)
def test_tomar_concurrente_no_duplica(api_conn, admin, token, almacen, basedatos):
    from conftest import dsn
    import psycopg
    from psycopg.rows import dict_row
    tok = queue.validar_token(admin, token["token"])
    ids = [alta(api_conn, tok, "KAMX", dia_unico(), 1)["id"] for i in range(6)]
    admin.execute("UPDATE control.jobs SET state='cancelled' WHERE state='queued' AND id <> ALL(%s)", (ids,))
    tomados, lock = [], threading.Lock()

    def hilo(n):
        with psycopg.connect(dsn(basedatos, "jobs_runner", "runner-pw"), autocommit=True, row_factory=dict_row) as c:
            while (j := queue.tomar(c, f"r{n}")):
                with lock:
                    tomados.append(j["id"])

    ts = [threading.Thread(target=hilo, args=(i,)) for i in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(tomados) == sorted(ids)
    limpiar(api_conn, almacen, *ids)


def test_runner_no_puede_tocar_cuotas_ni_tokens_ni_crear_schemas(runner_conn):
    import psycopg
    for sql in ("SELECT * FROM control.access_tokens", "UPDATE control.jobs SET expires_at = now() + interval '99 days'",
                "UPDATE control.jobs SET cancel_requested = false", "CREATE SCHEMA job_nuevo", "CREATE ROLE intruso",
                "DELETE FROM control.jobs"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            runner_conn.execute(sql)


def test_cancelar_en_marcha_se_ve_en_el_latido(api_conn, runner_conn, admin, token, almacen):
    tok = queue.validar_token(admin, token["token"])
    j = alta(api_conn, tok)
    admin.execute("UPDATE control.jobs SET state='cancelled' WHERE state='queued' AND id <> %s", (j["id"],))
    got = queue.tomar(runner_conn, "r1")
    assert got["id"] == j["id"]
    queue.empezar(runner_conn, j["id"], "r1")
    assert queue.latir(runner_conn, j["id"], "r1") is False
    assert queue.cancelar(api_conn, j["id"]) == "cancel_requested"
    assert queue.latir(runner_conn, j["id"], "r1") is True
    queue.terminar(runner_conn, j["id"], "r1", cancelado=True)
    assert queue.obtener(api_conn, j["id"])["state"] == "cancelled"
    assert queue.cancelar(api_conn, j["id"]) == "cancelled"  # cancelar dos veces no rompe
    sweep.barrer(api_conn, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)


def test_runner_que_pierde_el_job_lo_sabe(api_conn, runner_conn, admin, token, almacen):
    tok = queue.validar_token(admin, token["token"])
    j = alta(api_conn, tok)
    admin.execute("UPDATE control.jobs SET state='cancelled' WHERE state='queued' AND id <> %s", (j["id"],))
    queue.tomar(runner_conn, "r1")
    assert queue.latir(runner_conn, j["id"], "otro-runner") is True  # no es suyo: que pare
    limpiar(api_conn, almacen, j["id"])


def test_runner_muerto_vuelve_a_la_cola_con_schema_limpio_y_a_los_dos_intentos_falla(api_conn, runner_conn, admin, token, almacen):
    tok = queue.validar_token(admin, token["token"])
    j = alta(api_conn, tok)
    jid = j["id"]
    admin.execute("UPDATE control.jobs SET state='cancelled' WHERE state='queued' AND id <> %s", (jid,))
    queue.tomar(runner_conn, "r1")
    # el intento muerto dejó una fila publicada a medias en el schema
    import psycopg
    from conftest import dsn
    admin.execute(f"INSERT INTO {tenancy.schema_de(jid)}.radars VALUES ('AMX','KAMX',1,1,1,'p','a','b')")
    almacen.s3.put_object(Bucket="cogs", Key="AMX/N0B/x.tif", Body=b"x")
    admin.execute(f"INSERT INTO {tenancy.schema_de(jid)}.products VALUES (153,'N0B','dBZ','raster')")
    admin.execute(f"""INSERT INTO {tenancy.schema_de(jid)}.rasters (site_id,product_code,vol_time,r2_key,size_bytes,value_scale,value_offset,width,height,cell_m,created_at)
                      VALUES ('AMX',153,'t','AMX/N0B/x.tif',1,1,0,1,1,1,'t')""")
    admin.execute("UPDATE control.jobs SET heartbeat_at = now() - interval '1 hour' WHERE id=%s", (jid,))
    r = sweep.barrer(api_conn, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro, timeout_s=60)
    assert r["requeued"] == [jid]
    assert queue.obtener(api_conn, jid)["state"] == "queued"
    assert admin.execute(f"SELECT count(*) AS n FROM {tenancy.schema_de(jid)}.radars").fetchone()["n"] == 0
    assert "Contents" not in almacen.s3.list_objects_v2(Bucket="cogs")
    # segundo intento, también muere: failed, no vuelve a la cola
    queue.tomar(runner_conn, "r2")
    admin.execute("UPDATE control.jobs SET heartbeat_at = now() - interval '1 hour' WHERE id=%s", (jid,))
    r = sweep.barrer(api_conn, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro, timeout_s=60)
    assert r["failed"] == [jid]
    assert queue.obtener(api_conn, jid)["state"] == "failed"
    limpiar(api_conn, almacen, jid)
