import os

import pytest
from fastapi.testclient import TestClient

from conftest import MIGRACIONES, SECRETS, dsn
from lamula_jobs import solicitudes
from lamula_jobs.api import create_app
from lamula_jobs.mail import EnvioFallido, Mailer

FORM = {"content-type": "application/x-www-form-urlencoded"}


class Falso(Mailer):
    def __init__(self, falla=False):
        super().__init__("console", 0, "", "", "demo@test")
        self.falla = falla

    def enviar(self, para, asunto, texto, *, responder_a=None):
        if self.falla:
            raise EnvioFallido("smtp caído")
        self.enviados.append((para, asunto, texto))


@pytest.fixture
def ent(basedatos, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "dueno@test")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://jobs.test")
    monkeypatch.setenv("DEMO_URL", "https://demo.test/demo")
    m = Falso()
    app = create_app(dsn(basedatos, "jobs_api", "api-pw"), SECRETS, MIGRACIONES, mailer=m, verificar_turnstile=lambda t, ip: t == "ok")
    c = TestClient(app)
    c.headers["cf-connecting-ip"] = os.urandom(4).hex()  # el límite por IP vale para toda la base de la sesión
    return c, m


def cuerpo(email="a@b.org", **k):
    return {"email": email, "org": "Univ", "interes": ["huracan"], "acepta_aviso": True, "turnstile": "ok", **k}


def enlace_de(m):
    return m.enviados[-1][2].split("/v1/requests/")[1].split("/review")[0]


def test_flujo_completo_aprueba_y_el_token_llega_y_funciona(ent, admin):
    c, m = ent
    assert c.post("/v1/public/requests", json=cuerpo("flujo@b.org")).status_code == 202
    assert m.enviados[0][0] == "dueno@test"
    enl = enlace_de(m)
    assert c.get(f"/v1/requests/{enl}/review").status_code == 200  # GET solo muestra
    assert admin.execute("SELECT state FROM control.access_requests WHERE email='flujo@b.org'").fetchone()["state"] == "pending"
    r = c.post(f"/v1/requests/{enl}/approve", content="tier=demo", headers=FORM)
    assert r.status_code == 200, r.text
    para, _, texto = m.enviados[-1]
    assert para == "flujo@b.org"
    tok = [p for p in texto.split() if p.startswith("lma_")][0]
    assert c.get("/v1/jobs", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    assert c.get(f"/v1/requests/{enl}/review").status_code == 410  # un solo uso
    assert c.post(f"/v1/requests/{enl}/approve", content="tier=demo", headers=FORM).status_code == 410


def test_rechazo_no_emite_token_y_avisa_solo_si_se_pide(ent, admin):
    c, m = ent
    c.post("/v1/public/requests", json=cuerpo("rech@b.org"))
    n = len(m.enviados)
    assert c.post(f"/v1/requests/{enlace_de(m)}/reject", content="", headers=FORM).status_code == 200
    assert len(m.enviados) == n
    assert admin.execute("SELECT count(*) n FROM control.access_tokens WHERE email='rech@b.org'").fetchone()["n"] == 0
    c.post("/v1/public/requests", json=cuerpo("rech@b.org"))  # tras rechazar puede volver a pedir
    assert c.post(f"/v1/requests/{enlace_de(m)}/reject", content="avisar=1", headers=FORM).status_code == 200
    assert m.enviados[-1][0] == "rech@b.org"


def test_si_el_correo_falla_no_queda_token_y_sigue_pendiente(ent, admin):
    c, m = ent
    c.post("/v1/public/requests", json=cuerpo("falla@b.org"))
    enl = enlace_de(m)
    m.falla = True
    assert c.post(f"/v1/requests/{enl}/approve", content="tier=demo", headers=FORM).status_code == 502
    assert admin.execute("SELECT count(*) n FROM control.access_tokens WHERE email='falla@b.org'").fetchone()["n"] == 0
    assert admin.execute("SELECT state FROM control.access_requests WHERE email='falla@b.org'").fetchone()["state"] == "pending"
    m.falla = False
    assert c.post(f"/v1/requests/{enl}/approve", content="tier=demo", headers=FORM).status_code == 200


def test_validaciones_captcha_duplicado_y_niveles(ent, admin):
    c, m = ent
    assert c.post("/v1/public/requests", json=cuerpo(turnstile="mal")).status_code == 403
    assert c.post("/v1/public/requests", json=cuerpo(acepta_aviso=False)).status_code == 422
    assert c.post("/v1/public/requests", json=cuerpo("no-es-correo")).status_code == 422
    assert c.post("/v1/public/requests", json=cuerpo(interes=["x"])).status_code == 422
    assert c.post("/v1/public/requests", json=cuerpo("dup@b.org")).status_code == 202
    n = len(m.enviados)
    assert c.post("/v1/public/requests", json=cuerpo("DUP@b.org")).status_code == 202  # misma respuesta, sin segundo aviso
    assert len(m.enviados) == n
    assert c.post(f"/v1/requests/{enlace_de(m)}/approve", content="tier=interno", headers=FORM).status_code == 422  # nunca a terceros
    assert c.get("/v1/requests/lmq_inventado/review").status_code == 410


def test_limite_por_ip_y_html_escapado(ent, admin):
    c, m = ent
    h = {"cf-connecting-ip": "9.9.9.9"}
    for i in range(solicitudes.MAX_POR_IP_DIA):
        assert c.post("/v1/public/requests", json=cuerpo(f"ip{i}@b.org", org="<script>x</script>"), headers=h).status_code == 202
    assert c.post("/v1/public/requests", json=cuerpo("ip9@b.org"), headers=h).status_code == 429
    pag = c.get(f"/v1/requests/{enlace_de(m)}/review").text
    assert "<script>x" not in pag and "&lt;script&gt;" in pag


def test_caduca_el_enlace(ent, admin):
    c, m = ent
    c.post("/v1/public/requests", json=cuerpo("cad@b.org"))
    admin.execute("UPDATE control.access_requests SET review_expires_at = now() - interval '1 second' WHERE email='cad@b.org'")
    assert c.get(f"/v1/requests/{enlace_de(m)}/review").status_code == 410


def test_sin_secreto_de_turnstile_el_formulario_esta_cerrado(basedatos, monkeypatch):
    monkeypatch.delenv("TURNSTILE_SECRET", raising=False)
    c = TestClient(create_app(dsn(basedatos, "jobs_api", "api-pw"), SECRETS, MIGRACIONES, mailer=Falso()))
    assert c.post("/v1/public/requests", json=cuerpo()).status_code == 503
