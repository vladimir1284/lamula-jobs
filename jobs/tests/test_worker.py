"""Las comprobaciones puras del worker. El camino completo con el ORPG está en e2e/."""

from datetime import datetime, timezone

import psycopg
import pytest

from conftest import MIGRACIONES, SECRETS, dsn
from lamula_jobs import tenancy, worker
from lamula_jobs.ids import ulid

DAT = "kmlb,28113,-80654,116,302,MELBOURNE\nkamx,25611,-80413,4,131,MIAMI\nkhgx,29472,-95079,18,150,HOUSTON\n"


def test_coordenadas_esperadas(tmp_path):
    f = tmp_path / "change_radar.dat"
    f.write_text(DAT)
    assert worker.coordenadas_esperadas(f, "KAMX") == (25.611, -80.413)
    assert worker.coordenadas_esperadas(f, "khgx") == (29.472, -95.079)
    with pytest.raises(worker.JobFallido, match="no está"):
        worker.coordenadas_esperadas(f, "KXXX")


@pytest.fixture
def rw(api_conn, basedatos):
    jid = ulid()
    tenancy.crear(api_conn, jid, migraciones=MIGRACIONES, rw_secret=SECRETS.rw, ro_secret=SECRETS.ro)
    c = psycopg.connect(dsn(basedatos, tenancy.rol_rw(jid), tenancy.password(SECRETS.rw, "rw", jid)), autocommit=True,
                        row_factory=psycopg.rows.dict_row)
    yield c
    c.close()
    tenancy.borrar(api_conn, jid)


def radar(rw, site, lat, lon, icao=None):
    rw.execute("INSERT INTO radars VALUES (%s,%s,%s,%s,4,'p','a','b')", (site, icao, lat, lon))


def test_verificar_acepta_el_sitio_y_las_coordenadas_del_job(rw):
    radar(rw, "AMX", 25.6112, -80.4129)
    worker.verificar_coordenadas(rw, "KAMX", (25.611, -80.413))


@pytest.mark.parametrize("site,lat,lon,msg", [
    ("HGX", 25.611, -80.413, "radars dice HGX"),               # sitio ajeno
    ("AMX", 29.472, -95.079, "change_radar no surtió efecto"),  # sitio bien, coordenadas del vecino
    ("AMX", 25.611, -80.40, "change_radar no surtió efecto"),   # desvío de 13 milésimas
])
def test_verificar_rechaza_sitio_o_coordenadas_equivocados(rw, site, lat, lon, msg):
    radar(rw, site, lat, lon)
    with pytest.raises(worker.JobFallido, match=msg):
        worker.verificar_coordenadas(rw, "KAMX", (25.611, -80.413))


def test_verificar_rechaza_mas_de_un_radar_o_ninguno(rw):
    with pytest.raises(worker.JobFallido, match="1 fila"):
        worker.verificar_coordenadas(rw, "KAMX", (25.611, -80.413))
    radar(rw, "AMX", 25.611, -80.413)
    radar(rw, "HGX", 29.472, -95.079)
    with pytest.raises(worker.JobFallido, match="1 fila"):
        worker.verificar_coordenadas(rw, "KAMX", (25.611, -80.413))


def test_bajar_entradas_falla_limpio_si_falta_una_clave(almacen, tmp_path):
    class Cfg:
        s3, staging_bucket = almacen.s3, "staging"

    almacen.s3.put_object(Bucket="staging", Key="staging/j/KAMX20170910_170248_V06", Body=b"x")
    worker.bajar_entradas(Cfg, [{"staging_key": "staging/j/KAMX20170910_170248_V06"}], tmp_path / "in")
    assert (tmp_path / "in/KAMX20170910_170248_V06").read_bytes() == b"x"
    with pytest.raises(worker.JobFallido, match="no se pudo bajar"):
        worker.bajar_entradas(Cfg, [{"staging_key": "staging/j/no-existe"}], tmp_path / "in2")


def test_publicador_publica_por_lotes_y_no_repite(tmp_path):
    prod = tmp_path / "prod"
    prod.mkdir()
    vistos, tras = [], []

    def publicar(lote):
        vistos.append(sorted(p.name for p in lote.iterdir()))
        return len(vistos[-1]), 0

    pub = worker.Publicador(prod, tmp_path, publicar, lambda: tras.append(1))
    assert pub.paso() == 0 and not vistos                       # nada que publicar: no se llama
    (prod / "a").write_bytes(b"1")
    (prod / "b").write_bytes(b"2")
    assert pub.paso() == 2 and vistos == [["a", "b"]]
    (prod / "c").write_bytes(b"3")
    assert pub.paso() == 1 and vistos[-1] == ["c"]              # solo lo nuevo
    assert pub.paso() == 0 and len(vistos) == 2
    assert pub.procesados == 3 and pub.lotes == 2 and len(tras) == 2
    assert sorted(p.name for p in prod.iterdir()) == ["a", "b", "c"]  # prod no se consume: el lote es una copia
    assert not list(tmp_path.glob("lote-*"))                    # y los lotes se limpian


def test_publicador_falla_con_fallidos_y_respeta_la_cancelacion(tmp_path):
    prod = tmp_path / "prod"
    prod.mkdir()
    (prod / "a").write_bytes(b"1")
    pub = worker.Publicador(prod, tmp_path, lambda lote: (1, 1), lambda: None)
    with pytest.raises(worker.JobFallido, match="1 fallidos"):
        pub.paso()
    assert pub.procesados == 0                                  # un lote malo no cuenta
    cancelado = worker.Publicador(prod, tmp_path, lambda lote: (1, 0), lambda: None, cancelado=lambda: True)
    with pytest.raises(worker.JobCancelado):
        cancelado.paso()
