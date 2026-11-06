"""Alta de un job de punta a punta: cuotas, fila en la cola, schema y roles. Lo usan la API y los tests."""

from __future__ import annotations

from pathlib import Path

import psycopg

from . import queue, tenancy
from .config import Secrets
from .ids import token_resultado


def crear_job(conn: psycopg.Connection, tok: dict, *, icao: str, entradas: list[queue.Entrada], secrets: Secrets, migraciones: Path,
              caso: str | None = None) -> dict:
    job = queue.crear(conn, tok, icao=icao, entradas=entradas, caso=caso,
                      result_token_de=lambda jid: token_resultado(secrets.result, jid))
    if caso:  # D19: los datos van a la base de casos, que no lleva schema ni roles por job
        queue.publicar(conn, job["id"])
        return queue.obtener(conn, job["id"])
    try:
        tenancy.crear(conn, job["id"], migraciones=migraciones, rw_secret=secrets.rw, ro_secret=secrets.ro)
    except BaseException:
        # Sin schema el job no puede correr: no se deja en la cola ni se deja medio creado.
        tenancy.borrar(conn, job["id"])
        conn.execute("DELETE FROM control.jobs WHERE id = %s", (job["id"],))
        raise
    queue.publicar(conn, job["id"])
    return queue.obtener(conn, job["id"])


def token_de_sistema(conn: psycopg.Connection) -> dict:
    """Token del nivel `casos`, propio de `jobs-admin`: se crea la primera vez y nadie conoce su valor."""
    from .ids import nuevo_token_acceso, sha256, ulid
    fila = conn.execute("SELECT id FROM control.access_tokens WHERE note = 'sistema:casos' AND revoked_at IS NULL").fetchone()
    if fila is None:
        conn.execute("INSERT INTO control.access_tokens (id, email, token_sha256, tier, note) VALUES (%s,'sistema@casos',%s,'casos','sistema:casos')",
                     (ulid(), sha256(nuevo_token_acceso())))
    return conn.execute(
        """SELECT t.*, x.max_volumes, x.max_jobs_total, x.max_jobs_active, x.retention_days, x.priority, x.max_bytes
             FROM control.access_tokens t JOIN control.tiers x ON x.name = t.tier
            WHERE t.note = 'sistema:casos' AND t.revoked_at IS NULL""").fetchone()


def lanzar_caso(conn: psycopg.Connection, nombre: str, s3, *, secrets: Secrets, migraciones: Path) -> dict:
    """Procesa un caso preparado, una sola vez (D19): sin caducidad, con datos en la base y el bucket de casos."""
    from . import catalogo
    if nombre not in catalogo.CASOS:
        raise KeyError(nombre)
    c = catalogo.caso(s3, nombre)
    if not c["volumes"]:
        raise queue.EntradaInvalida(f"el caso {nombre} no tiene volúmenes en la fuente pública")
    entradas = [queue.Entrada(v["key"], v["bytes"], v["key"]) for v in c["volumes"]]
    return crear_job(conn, token_de_sistema(conn), icao=c["icao"], entradas=entradas, secrets=secrets, migraciones=migraciones, caso=nombre)
