"""jobs-api: la única cara pública. Valida token, aplica cuotas, crea jobs y sirve su estado.

No procesa nada y no habla con el ORPG. Una conexión por petición: el volumen del demo (una
decena de prospectos) no justifica un pool, y así un fallo de Postgres no deja conexiones colgando.
"""

from __future__ import annotations

import hmac
import html
import os
import urllib.parse
from contextlib import contextmanager
from pathlib import Path

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import catalogo, queue, service, solicitudes, tenancy
from .mail import EnvioFallido, Mailer
from .config import Secrets, env
from .db import conectar
from .ids import token_resultado


class EntradaIn(BaseModel):
    staging_key: str | None = Field(default=None, min_length=1, max_length=512)
    bytes: int = Field(default=0, ge=0)
    source_key: str | None = None


class JobIn(BaseModel):
    icao: str
    inputs: list[EntradaIn]


def _publico(j: dict, secrets: Secrets) -> dict:
    return {
        "id": j["id"], "state": j["state"], "icao": j["icao"], "n_volumes": j["n_volumes"],
        "vol_from": j["vol_from"], "vol_to": j["vol_to"], "created_at": j["created_at"],
        "started_at": j["started_at"], "finished_at": j["finished_at"], "expires_at": j["expires_at"],
        "error": j["error"], "cancel_requested": j["cancel_requested"],
        "result_token": token_resultado(secrets.result, j["id"]),
    }


class SolicitudIn(BaseModel):
    email: str = Field(max_length=320)
    org: str = Field(max_length=200)
    cargo: str | None = Field(default=None, max_length=120)
    interes: list[str] = Field(max_length=4)
    radar: str | None = Field(default=None, max_length=120)
    comentario: str | None = Field(default=None, max_length=2000)
    acepta_aviso: bool
    turnstile: str = Field(max_length=2048)


def create_app(dsn: str | None = None, secrets: Secrets | None = None, migraciones: Path | None = None,
               internal_key: str | None = None, s3_catalogo=None, mailer: Mailer | None = None, verificar_turnstile=None) -> FastAPI:
    dsn = dsn or env("JOBS_API_DSN")
    secrets = secrets or Secrets.from_env()
    migraciones = migraciones or Path(env("PIPELINE_MIGRATIONS"))
    internal_key = internal_key or os.environ.get("JOBS_INTERNAL_KEY", "")
    app = FastAPI(title="LAMULA jobs-api", docs_url=None, redoc_url=None)

    @contextmanager
    def _conn():
        c = conectar(dsn)
        try:
            yield c
        finally:
            c.close()

    def token(authorization: str | None = Header(default=None)) -> dict:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "falta el token de acceso")
        with _conn() as c:
            t = queue.validar_token(c, authorization[7:])
        if t is None:
            raise HTTPException(401, "token no válido, caducado o revocado")
        return t

    def _s3():
        nonlocal s3_catalogo
        if s3_catalogo is None:
            s3_catalogo = catalogo.anonimo()
        return s3_catalogo

    def _cat(fn, *a):
        try:
            return fn(_s3(), *a)
        except catalogo.CatalogoError as exc:
            raise HTTPException(422, str(exc))
        except Exception:
            raise HTTPException(502, "el catálogo público no responde")

    @app.get("/v1/catalog/sites")
    def cat_sitios(day: str, tok: dict = Depends(token)) -> dict:
        return {"day": day, "sites": _cat(catalogo.sitios, day)}

    @app.get("/v1/catalog/volumes")
    def cat_volumenes(site: str, day: str, tok: dict = Depends(token)) -> dict:
        vs = _cat(catalogo.volumenes, site, day)
        return {"site": site.upper(), "day": day, "volumes": [{"key": v.key, "bytes": v.bytes, "time": v.hora.isoformat()} for v in vs],
                "estimate": catalogo.estimar(len(vs), sum(v.bytes for v in vs))}

    @app.get("/v1/catalog/cases")
    def cat_casos(tok: dict = Depends(token)) -> list[dict]:
        return [{"id": k, "titulo": t, "icao": i, "desde": d, "hasta": h} for k, (t, i, d, h) in catalogo.CASOS.items()]

    @app.get("/v1/catalog/cases/{nombre}")
    def cat_caso(nombre: str, tok: dict = Depends(token)) -> dict:
        if nombre not in catalogo.CASOS:
            raise HTTPException(404, "no existe")
        return _cat(catalogo.caso, nombre)

    @app.get("/v1/public/cases")
    def casos_listos() -> list[dict]:
        """Casos preparados ya procesados (D19). Sin token: son públicos y de solo lectura. Solo los `ready`."""
        with _conn() as c:
            filas = c.execute("SELECT caso, vol_from, vol_to, n_volumes FROM control.jobs WHERE destino = 'casos' AND state = 'ready'").fetchall()
        return [{"id": f["caso"], "titulo": catalogo.CASOS[f["caso"]][0], "icao": catalogo.CASOS[f["caso"]][1],
                "site_id": catalogo.CASOS[f["caso"]][1][1:],  # id de 3 letras del pipeline y del viewer (worker.py: icao[1:])
                 "desde": f["vol_from"].isoformat(), "hasta": f["vol_to"].isoformat(), "n_volumes": f["n_volumes"]}
                for f in filas if f["caso"] in catalogo.CASOS]

    def _mailer() -> Mailer:
        nonlocal mailer
        if mailer is None:
            mailer = Mailer.from_env()
        return mailer

    def _turnstile(tk: str, ip: str | None) -> bool:
        if verificar_turnstile is not None:
            return verificar_turnstile(tk, ip)
        import json as _json
        import urllib.request
        secreto = os.environ.get("TURNSTILE_SECRET")
        if not secreto:
            raise HTTPException(503, "el formulario no está configurado")  # cerrado por defecto: sin secreto no se acepta nada
        datos = urllib.parse.urlencode({"secret": secreto, "response": tk, **({"remoteip": ip} if ip else {})}).encode()
        try:
            with urllib.request.urlopen("https://challenges.cloudflare.com/turnstile/v0/siteverify", datos, timeout=10) as r:
                return bool(_json.load(r).get("success"))
        except Exception:
            raise HTTPException(502, "no se pudo verificar el captcha")

    def _ip(req: Request) -> str | None:
        return req.headers.get("cf-connecting-ip") or (req.client.host if req.client else None)

    @app.post("/v1/public/requests", status_code=202)
    def solicitar(body: SolicitudIn, req: Request) -> dict:
        """Formulario público. Misma respuesta si el correo ya tenía una pendiente, para no revelarlo."""
        ip = _ip(req)
        if not body.acepta_aviso:
            raise HTTPException(422, "hay que aceptar el aviso de uso")
        if not _turnstile(body.turnstile, ip):
            raise HTTPException(403, "captcha no válido")
        with _conn() as c:
            try:
                rid, enlace = solicitudes.crear(c, email=body.email, org=body.org, cargo=body.cargo, interes=body.interes,
                                                radar=body.radar, comentario=body.comentario, ip=ip)
            except solicitudes.SolicitudInvalida as exc:
                raise HTTPException(422, str(exc))
            except solicitudes.Demasiadas as exc:
                if "pendiente" in str(exc):
                    return {"recibida": True}
                raise HTTPException(429, str(exc))
            solicitudes.avisar_al_dueno(c, _mailer(), rid=rid, enlace=enlace, admin_email=env("ADMIN_EMAIL"), base_url=env("PUBLIC_BASE_URL"))
        return {"recibida": True}

    def _pagina(titulo: str, cuerpo: str, status: int = 200) -> HTMLResponse:
        h = (f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
             f'<meta name="robots" content="noindex"><title>{html.escape(titulo)}</title>'
             f'<body style="font:16px system-ui;max-width:34rem;margin:2rem auto;padding:0 1rem"><h1 style="font-size:1.3rem">{html.escape(titulo)}</h1>{cuerpo}')
        return HTMLResponse(h, status, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    def _revision(enlace: str) -> dict:
        with _conn() as c:
            try:
                return solicitudes.por_enlace(c, enlace)
            except solicitudes.NoResoluble:
                raise HTTPException(410, "este enlace ya no vale: la solicitud está resuelta o caducó")

    @app.get("/v1/requests/{enlace}/review", response_class=HTMLResponse)
    def revisar(enlace: str) -> HTMLResponse:
        # GET solo muestra: los antivirus y previsualizadores abren enlaces, y no pueden aprobar nada.
        s = _revision(enlace)
        e = html.escape
        niveles = "".join(f'<option value="{n}">{n}</option>' for n in solicitudes.NIVELES_A_TERCEROS)
        cuerpo = (f"<p><b>{e(s['email'])}</b><br>{e(s['org'])} · {e(s['cargo'] or '-')}</p>"
                  f"<p>Quiere ver: {e(', '.join(s['interes']))}<br>Radar o zona: {e(s['radar'] or '-')}</p>"
                  f"<p style='white-space:pre-wrap'>{e(s['comentario'] or '')}</p>"
                  f"<form method='post' action='/v1/requests/{e(enlace)}/approve'><label>Nivel <select name='tier'>{niveles}</select></label> "
                  f"<button>Aprobar y enviar el token</button></form><hr>"
                  f"<form method='post' action='/v1/requests/{e(enlace)}/reject'><label><input type='checkbox' name='avisar' value='1'> avisar al solicitante</label> "
                  f"<button>Rechazar</button></form>")
        return _pagina("Solicitud de acceso", cuerpo)

    async def _form(req: Request) -> dict[str, str]:
        return {k: v[0] for k, v in urllib.parse.parse_qs((await req.body()).decode(errors="replace")).items()}

    @app.post("/v1/requests/{enlace}/approve", response_class=HTMLResponse)
    async def aprobar(enlace: str, req: Request) -> HTMLResponse:
        s = _revision(enlace)
        tier = (await _form(req)).get("tier", "demo")
        with _conn() as c:
            try:
                solicitudes.aprobar(c, s["id"], tier=tier, mailer=_mailer(), demo_url=env("DEMO_URL"))
            except solicitudes.SolicitudInvalida as exc:
                raise HTTPException(422, str(exc))
            except solicitudes.NoResoluble:
                raise HTTPException(410, "ya está resuelta")
            except EnvioFallido as exc:
                return _pagina("No se pudo enviar el correo", f"<p>No se emitió ningún token y la solicitud sigue pendiente. Reintenta.</p><p>{html.escape(str(exc))}</p>", 502)
        return _pagina("Aprobada", f"<p>Token de nivel {html.escape(tier)} enviado a {html.escape(s['email'])}.</p>")

    @app.post("/v1/requests/{enlace}/reject", response_class=HTMLResponse)
    async def rechazar(enlace: str, req: Request) -> HTMLResponse:
        s = _revision(enlace)
        avisar = (await _form(req)).get("avisar") == "1"
        with _conn() as c:
            try:
                solicitudes.rechazar(c, s["id"], avisar=avisar, mailer=_mailer())
            except solicitudes.NoResoluble:
                raise HTTPException(410, "ya está resuelta")
            except EnvioFallido as exc:
                return _pagina("No se pudo enviar el aviso", f"<p>La solicitud sigue pendiente.</p><p>{html.escape(str(exc))}</p>", 502)
        return _pagina("Rechazada", "<p>Hecho.</p>")

    @app.get("/healthz")
    def healthz() -> dict:
        with _conn() as c:
            c.execute("SELECT 1")
        return {"ok": True}

    def _entradas_fuente(icao: str, claves: list[str]) -> list[queue.Entrada]:
        """Valida contra el catálogo público (existe, es V06, es del radar) y fija los tamaños reales."""
        try:
            dias = sorted({"-".join(k.split("/")[:3]) for k in claves})
            if not all(catalogo.CLAVE.match(k) and k.split("/")[3] == icao for k in claves):
                raise HTTPException(422, f"las claves tienen que ser volúmenes _V06 del catálogo público de {icao}")
            tam = {v.key: v.bytes for d in dias for v in catalogo.volumenes(_s3(), icao, d)}
        except catalogo.CatalogoError as exc:
            raise HTTPException(422, str(exc))
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502, "el catálogo público no responde")
        falta = [k for k in claves if k not in tam]
        if falta:
            raise HTTPException(422, f"no existe en el catálogo público: {falta[0]}")
        return [queue.Entrada(k, tam[k], k) for k in claves]

    @app.post("/v1/jobs", status_code=201)
    def alta(body: JobIn, tok: dict = Depends(token)) -> dict:
        if any((e.staging_key is None) == (e.source_key is None) for e in body.inputs):
            raise HTTPException(422, "cada entrada lleva staging_key o source_key, una de las dos")
        icao = body.icao.upper()
        if any(e.source_key for e in body.inputs):
            if not all(e.source_key for e in body.inputs):
                raise HTTPException(422, "no se mezclan entradas de staging y de la fuente pública")
            ents = _entradas_fuente(icao, [e.source_key for e in body.inputs])
        else:
            ents = [queue.Entrada(e.staging_key, e.bytes, e.source_key) for e in body.inputs]
        with _conn() as c:
            try:
                j = service.crear_job(c, tok, icao=icao, entradas=ents, secrets=secrets, migraciones=migraciones)
            except queue.EntradaInvalida as exc:
                raise HTTPException(422, str(exc))
            except queue.CuotaExcedida as exc:
                raise HTTPException(429, str(exc))
            except queue.Solapado as exc:
                raise HTTPException(409, str(exc))
        return _publico(j, secrets)

    def _propio(c: psycopg.Connection, job_id: str, tok: dict) -> dict:
        try:
            j = queue.obtener(c, job_id)
        except KeyError:
            raise HTTPException(404, "no existe")
        if j["token_id"] != tok["id"]:
            raise HTTPException(404, "no existe")  # no se distingue «ajeno» de «inexistente»
        return j

    @app.get("/v1/jobs")
    def lista(tok: dict = Depends(token)) -> list[dict]:
        with _conn() as c:
            rows = c.execute("SELECT * FROM control.jobs WHERE token_id = %s ORDER BY created_at DESC LIMIT 100", (tok["id"],)).fetchall()
        return [_publico(j, secrets) for j in rows]

    @app.get("/v1/jobs/{job_id}")
    def estado(job_id: str, tok: dict = Depends(token)) -> dict:
        with _conn() as c:
            return _publico(_propio(c, job_id, tok), secrets)

    @app.post("/v1/jobs/{job_id}/cancel")
    def cancela(job_id: str, tok: dict = Depends(token)) -> dict:
        with _conn() as c:
            _propio(c, job_id, tok)
            return {"state": queue.cancelar(c, job_id)}

    @app.get("/v1/results/{rtoken}")
    def resultado(rtoken: str, x_internal_key: str | None = Header(default=None)) -> dict:
        """Para el viewer demo (servidor a servidor): del token de resultado a las credenciales de solo lectura."""
        if not internal_key or not x_internal_key or not hmac.compare_digest(x_internal_key, internal_key):
            raise HTTPException(401, "solo servidor a servidor")
        from .ids import sha256
        with _conn() as c:
            j = c.execute("SELECT * FROM control.jobs WHERE result_token_sha256 = %s", (sha256(rtoken),)).fetchone()
            if j is None or j["resources_dropped_at"] is not None or j["state"] in ("creating", "expired", "cancelled"):
                raise HTTPException(404, "no existe o caducó")
        return {
            "job_id": j["id"], "state": j["state"], "vol_from": j["vol_from"], "vol_to": j["vol_to"], "expires_at": j["expires_at"],
            "pg_user": tenancy.rol_ro(j["id"]), "pg_password": tenancy.password(secrets.ro, "ro", j["id"]),
        }

    return app
