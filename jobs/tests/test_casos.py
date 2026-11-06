"""D19: los casos preparados se procesan una vez, no caducan y no llevan schema ni roles por job."""

import boto3
import psycopg
import pytest
from moto import mock_aws

from conftest import MIGRACIONES, SECRETS, claves, dia_unico
from lamula_jobs import queue, service, sweep, tenancy
from lamula_jobs.worker import Cfg, Destino, JobFallido

CLAVES = ["2017/09/10/KAMX/KAMX20170910_170000_V06", "2017/09/10/KAMX/KAMX20170910_170600_V06"]


@pytest.fixture
def fuente():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="unidata-nexrad-level2")
        for k in CLAVES:
            s3.put_object(Bucket="unidata-nexrad-level2", Key=k, Body=b"x" * 10)
        yield s3


def lanzar(api_conn, fuente, nombre="irma"):
    return service.lanzar_caso(api_conn, nombre, fuente, secrets=SECRETS, migraciones=MIGRACIONES)


def test_un_caso_no_caduca_ni_lleva_schema_y_solo_se_procesa_una_vez(api_conn, admin, fuente, almacen):
    j = lanzar(api_conn, fuente)
    try:
        assert (j["destino"], j["caso"], j["state"], j["expires_at"], j["n_volumes"]) == ("casos", "irma", "queued", None, 2)
        assert not admin.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (tenancy.schema_de(j["id"]),)).fetchone()
        assert [e["source_key"] for e in queue.entradas_de(admin, j["id"])] == CLAVES
        with pytest.raises(queue.Solapado):  # el guardián de D14 lo ve antes que el índice único
            lanzar(api_conn, fuente)
        with pytest.raises(psycopg.errors.UniqueViolation, match="jobs_un_caso_vivo"):  # red de seguridad, a mano
            admin.execute("UPDATE control.jobs SET state='queued' WHERE id=%s", (j["id"],))
            admin.execute("""INSERT INTO control.jobs (id, token_id, state, icao, vol_from, vol_to, n_volumes, total_bytes, priority,
                               result_token_sha256, expires_at, destino, caso)
                               SELECT 'x'||id, token_id, state, 'KHGX', vol_from, vol_to, 1, 0, 0, 'otro', NULL, 'casos', caso
                                 FROM control.jobs WHERE id=%s""", (j["id"],))
        # El barrido no caduca un caso ready por mucho que pase el tiempo, ni toca nada en el almacén.
        admin.execute("UPDATE control.jobs SET state='ready' WHERE id=%s", (j["id"],))
        r = sweep.barrer(api_conn, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)
        assert j["id"] not in r["dropped"]
        assert queue.obtener(admin, j["id"])["state"] == "ready"
    finally:
        admin.execute("UPDATE control.jobs SET state='failed' WHERE id=%s", (j["id"],))  # un fallido libera el nombre


def test_caso_fallido_se_puede_repetir(api_conn, admin, fuente):
    j = lanzar(api_conn, fuente)
    admin.execute("UPDATE control.jobs SET state='failed' WHERE id=%s", (j["id"],))
    j2 = lanzar(api_conn, fuente)
    assert j2["id"] != j["id"]
    admin.execute("UPDATE control.jobs SET state='failed' WHERE id=%s", (j2["id"],))


def test_caso_inexistente_o_sin_volumenes(api_conn, fuente):
    with pytest.raises(KeyError):
        lanzar(api_conn, fuente, "zzz")
    with pytest.raises(queue.EntradaInvalida):
        lanzar(api_conn, fuente, "harvey")  # la fuente de la prueba no tiene KHGX ese día


def test_los_casos_no_chocan_con_los_jobs_normales(api_conn, admin, token, fuente):
    """D14 protege los objetos de UN bucket: casos y demo tienen buckets distintos, así que no se bloquean entre sí."""
    tok = queue.validar_token(admin, token["token"])
    dia = "20170910"
    ents = [queue.Entrada(f"staging/KAMX{dia}_170{m}00_V06", 10) for m in (0, 6)]
    j = service.crear_job(api_conn, tok, icao="KAMX", entradas=ents, secrets=SECRETS, migraciones=MIGRACIONES)
    try:
        c = lanzar(api_conn, fuente)
        admin.execute("UPDATE control.jobs SET state='failed' WHERE id=%s", (c["id"],))
    finally:
        admin.execute("UPDATE control.jobs SET state='cancelled' WHERE id=%s", (j["id"],))


def _cfg(casos):
    return Cfg(runner_dsn="", pg_host="h", pg_port="5432", pg_db="demo", secrets=SECRETS, s3=None, staging_bucket="s",
               r2_endpoint="e", r2_bucket="demo-raster", r2_key="k", r2_secret="s", casos=casos)


def test_el_worker_publica_cada_job_en_su_destino():
    casos = Destino("hc", "5433", "lamula_casos", "casos_rw", "pw", "casos-raster")
    cfg = _cfg(casos)
    assert cfg.destino_de({"id": "x", "destino": "casos"}) is casos
    jid = "01m6sfrpm3tz335gtmbr0yjqcw"
    d = cfg.destino_de({"id": jid, "destino": "demo"})
    assert (d.pg_db, d.pg_user, d.r2_bucket) == ("demo", tenancy.rol_rw(jid), "demo-raster")
    with pytest.raises(JobFallido, match="base de casos"):
        _cfg(None).destino_de({"id": jid, "destino": "casos"})


def test_casos_publicos_solo_los_ya_procesados(api_conn, admin, fuente, basedatos):
    from fastapi.testclient import TestClient
    from conftest import dsn
    from lamula_jobs.api import create_app
    cli = TestClient(create_app(dsn(basedatos, "jobs_api", "api-pw"), SECRETS, MIGRACIONES, internal_key="k", s3_catalogo=fuente))
    j = lanzar(api_conn, fuente)
    try:
        assert cli.get("/v1/public/cases").json() == []  # en cola: todavía no se enseña
        admin.execute("UPDATE control.jobs SET state='ready' WHERE id=%s", (j["id"],))
        r = cli.get("/v1/public/cases")  # sin cabecera de token
        assert r.status_code == 200
        (c,) = r.json()
        assert (c["id"], c["titulo"], c["icao"], c["n_volumes"]) == ("irma", "Irma", "KAMX", 2)
        assert c["desde"].startswith("2017-09-10T17:00") and "result_token" not in c
    finally:
        admin.execute("UPDATE control.jobs SET state='failed' WHERE id=%s", (j["id"],))
