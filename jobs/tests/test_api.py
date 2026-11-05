import pytest
from fastapi.testclient import TestClient

from conftest import MIGRACIONES, SECRETS, claves, dia_unico, dsn
from lamula_jobs import queue, sweep, tenancy
from lamula_jobs.api import create_app
from lamula_jobs.ids import token_resultado


@pytest.fixture
def cliente(basedatos):
    app = create_app(dsn(basedatos, "jobs_api", "api-pw"), SECRETS, MIGRACIONES, internal_key="clave-interna")
    return TestClient(app)


def cuerpo(icao="KAMX", n=2, dia=None):
    return {"icao": icao, "inputs": [{"staging_key": k, "bytes": 10} for k in claves(icao, dia or dia_unico(), n)]}


def H(t):
    return {"Authorization": f"Bearer {t}"}


def test_sin_token_o_con_token_malo(cliente):
    assert cliente.post("/v1/jobs", json=cuerpo()).status_code == 401
    assert cliente.post("/v1/jobs", json=cuerpo(), headers=H("lma_x")).status_code == 401
    assert cliente.get("/v1/jobs", headers={"Authorization": "Basic x"}).status_code == 401


def test_alta_estado_cancelacion_y_aislamiento_entre_tokens(cliente, token, admin, almacen):
    from lamula_jobs.admin import emitir
    _, otro = emitir(admin, email="otro@test", tier="evaluacion")
    r = cliente.post("/v1/jobs", json=cuerpo(), headers=H(token["token"]))
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["state"] == "queued" and j["result_token"] == token_resultado(SECRETS.result, j["id"])
    assert "token_sha256" not in j and "claimed_by" not in j
    assert cliente.get(f"/v1/jobs/{j['id']}", headers=H(token["token"])).json()["id"] == j["id"]
    assert [x["id"] for x in cliente.get("/v1/jobs", headers=H(token["token"])).json()] == [j["id"]]
    # el token ajeno ni lo ve ni lo cancela, y no se distingue de «no existe»
    assert cliente.get(f"/v1/jobs/{j['id']}", headers=H(otro)).status_code == 404
    assert cliente.post(f"/v1/jobs/{j['id']}/cancel", headers=H(otro)).status_code == 404
    assert cliente.get("/v1/jobs", headers=H(otro)).json() == []
    assert cliente.post(f"/v1/jobs/{j['id']}/cancel", headers=H(token["token"])).json() == {"state": "cancelled"}
    sweep.barrer(admin, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)


@pytest.mark.parametrize("token", ["demo"], indirect=True)
def test_codigos_de_error(cliente, token, admin, almacen):
    assert cliente.post("/v1/jobs", json=cuerpo(n=13), headers=H(token["token"])).status_code == 429
    assert cliente.post("/v1/jobs", json={"icao": "KAMX", "inputs": []}, headers=H(token["token"])).status_code == 422
    assert cliente.post("/v1/jobs", json={"icao": "KAMX"}, headers=H(token["token"])).status_code == 422
    b = cuerpo(n=2)
    ok = cliente.post("/v1/jobs", json=b, headers=H(token["token"]))
    assert ok.status_code == 201
    assert cliente.post("/v1/jobs", json=cuerpo(icao="KHGX"), headers=H(token["token"])).status_code == 429  # 1 activo
    cliente.post(f"/v1/jobs/{ok.json()['id']}/cancel", headers=H(token["token"]))
    sweep.barrer(admin, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)


def test_solapado_da_409(cliente, token, admin, almacen):
    b = cuerpo()
    a = cliente.post("/v1/jobs", json=b, headers=H(token["token"]))
    assert a.status_code == 201
    from lamula_jobs.admin import emitir
    _, otro = emitir(admin, email="otro2@test", tier="evaluacion")
    assert cliente.post("/v1/jobs", json=b, headers=H(otro)).status_code == 409
    cliente.post(f"/v1/jobs/{a.json()['id']}/cancel", headers=H(token["token"]))
    sweep.barrer(admin, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)


def test_resultado_solo_servidor_a_servidor_y_da_credenciales_de_solo_lectura(cliente, token, admin, almacen, basedatos):
    import psycopg
    j = cliente.post("/v1/jobs", json=cuerpo(), headers=H(token["token"])).json()
    url = f"/v1/results/{j['result_token']}"
    assert cliente.get(url).status_code == 401
    assert cliente.get(url, headers={"X-Internal-Key": "mala"}).status_code == 401
    r = cliente.get(url, headers={"X-Internal-Key": "clave-interna"})
    assert r.status_code == 200
    cred = r.json()
    assert cred["pg_user"] == tenancy.rol_ro(j["id"]) and "pg_password" in cred
    with psycopg.connect(dsn(basedatos, cred["pg_user"], cred["pg_password"]), autocommit=True) as c:
        assert c.execute("SELECT count(*) FROM radars").fetchone()[0] == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("INSERT INTO radars VALUES ('A','A',1,1,1,'p','a','b')")
    assert cliente.get("/v1/results/lmr_inventado", headers={"X-Internal-Key": "clave-interna"}).status_code == 404
    cliente.post(f"/v1/jobs/{j['id']}/cancel", headers=H(token["token"]))
    sweep.barrer(admin, almacen, migraciones=MIGRACIONES, rw=SECRETS.rw, ro=SECRETS.ro)
    # con el job cancelado y sus recursos borrados, el token de resultado ya no abre nada
    assert cliente.get(url, headers={"X-Internal-Key": "clave-interna"}).status_code == 404


def test_sin_clave_interna_configurada_el_endpoint_de_resultados_esta_cerrado(basedatos, token):
    c = TestClient(create_app(dsn(basedatos, "jobs_api", "api-pw"), SECRETS, MIGRACIONES, internal_key=""))
    assert c.get("/v1/results/lmr_x", headers={"X-Internal-Key": ""}).status_code == 401
