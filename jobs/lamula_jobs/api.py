"""jobs-api: la única cara pública. Valida token, aplica cuotas, crea jobs y sirve su estado.

No procesa nada y no habla con el ORPG. Una conexión por petición: el volumen del demo (una
decena de prospectos) no justifica un pool, y así un fallo de Postgres no deja conexiones colgando.
"""

from __future__ import annotations

import hmac
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from . import catalogo, queue, service, tenancy
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


def create_app(dsn: str | None = None, secrets: Secrets | None = None, migraciones: Path | None = None,
               internal_key: str | None = None, s3_catalogo=None) -> FastAPI:
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
                 "desde": f["vol_from"].isoformat(), "hasta": f["vol_to"].isoformat(), "n_volumes": f["n_volumes"]}
                for f in filas if f["caso"] in catalogo.CASOS]

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
