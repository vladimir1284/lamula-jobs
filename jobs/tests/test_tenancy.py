import psycopg
import pytest

from lamula_jobs import sweep, tenancy
from lamula_jobs.ids import ulid
from conftest import MIGRACIONES, SECRETS, dsn

INS_RADAR = "INSERT INTO radars VALUES ('AMX','KAMX',25.6,-80.4,4.0,'+proj=aeqd','2017-09-05T00:00:00','2017-09-05T00:00:00')"


def nuevo(api_conn):
    jid = ulid()
    tenancy.crear(api_conn, jid, migraciones=MIGRACIONES, rw_secret=SECRETS.rw, ro_secret=SECRETS.ro)
    return jid


def conectar_como(basedatos, jid, rol):
    pw = tenancy.password(SECRETS.rw if rol == "rw" else SECRETS.ro, rol, jid)
    user = tenancy.rol_rw(jid) if rol == "rw" else tenancy.rol_ro(jid)
    return psycopg.connect(dsn(basedatos, user, pw), autocommit=True)


def test_rw_escribe_sin_calificar_y_ro_solo_lee(api_conn, basedatos):
    jid = nuevo(api_conn)
    try:
        with conectar_como(basedatos, jid, "rw") as rw:
            rw.execute(INS_RADAR)  # sin schema delante: manda el search_path del rol
            assert rw.execute("SELECT count(*) FROM radars").fetchone()[0] == 1
            assert rw.execute("SELECT count(*) FROM mosaic_domains").fetchone()[0] == 0  # 0002 también
        with conectar_como(basedatos, jid, "ro") as ro:
            assert ro.execute("SELECT count(*) FROM radars").fetchone()[0] == 1
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                ro.execute("DELETE FROM radars")
    finally:
        tenancy.borrar(api_conn, jid)


def test_roles_no_ven_control_ni_otros_jobs_ni_alteran_el_schema(api_conn, basedatos):
    a, b = nuevo(api_conn), nuevo(api_conn)
    try:
        with conectar_como(basedatos, a, "rw") as rw:
            rw.execute(INS_RADAR)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                rw.execute("SELECT * FROM control.jobs")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                rw.execute(f"SELECT * FROM {tenancy.schema_de(b)}.radars")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                rw.execute("ALTER TABLE radars ADD COLUMN x int")  # las tablas no son suyas
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                rw.execute("CREATE TABLE intruso (x int)")
        with conectar_como(basedatos, b, "rw") as rw:
            assert rw.execute("SELECT count(*) FROM radars").fetchone()[0] == 0  # el otro no ve la fila de A
    finally:
        tenancy.borrar(api_conn, a)
        tenancy.borrar(api_conn, b)


def test_borrar_no_deja_nada_aunque_haya_conexiones_vivas(api_conn, basedatos, admin):
    jid = nuevo(api_conn)
    viva = conectar_como(basedatos, jid, "rw")
    viva.execute(INS_RADAR)
    tenancy.borrar(api_conn, jid)
    assert admin.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (tenancy.schema_de(jid),)).fetchone() is None
    assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname LIKE %s", (f"job\\_{jid}%",)).fetchone() is None
    viva.close()


def test_id_invalido_no_llega_a_sql(api_conn):
    with pytest.raises(ValueError):
        tenancy.crear(api_conn, "x; DROP SCHEMA control CASCADE", migraciones=MIGRACIONES, rw_secret=b"a", ro_secret=b"b")


def test_creacion_a_medias_se_recoge_con_borrar(api_conn, admin, tmp_path):
    """Migraciones que fallan a mitad: el schema y los roles quedan, y `borrar` los limpia."""
    mala = tmp_path / "m"
    mala.mkdir()
    (mala / "0001.sql").write_text("CREATE TABLE a (x int); SELECT * FROM no_existe;")
    jid = ulid()
    with pytest.raises(psycopg.errors.UndefinedTable):
        tenancy.crear(api_conn, jid, migraciones=mala, rw_secret=b"a", ro_secret=b"b")
    tenancy.borrar(api_conn, jid)
    h = tenancy.huerfanos(admin, set())
    assert not [x for x in h["schemas"] + h["roles"] if jid in x]
