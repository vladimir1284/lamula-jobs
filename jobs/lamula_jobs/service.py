"""Alta de un job de punta a punta: cuotas, fila en la cola, schema y roles. Lo usan la API y los tests."""

from __future__ import annotations

from pathlib import Path

import psycopg

from . import queue, tenancy
from .config import Secrets
from .ids import token_resultado


def crear_job(conn: psycopg.Connection, tok: dict, *, icao: str, entradas: list[queue.Entrada], secrets: Secrets, migraciones: Path) -> dict:
    job = queue.crear(conn, tok, icao=icao, entradas=entradas,
                      result_token_de=lambda jid: token_resultado(secrets.result, jid))
    try:
        tenancy.crear(conn, job["id"], migraciones=migraciones, rw_secret=secrets.rw, ro_secret=secrets.ro)
    except BaseException:
        # Sin schema el job no puede correr: no se deja en la cola ni se deja medio creado.
        tenancy.borrar(conn, job["id"])
        conn.execute("DELETE FROM control.jobs WHERE id = %s", (job["id"],))
        raise
    queue.publicar(conn, job["id"])
    return queue.obtener(conn, job["id"])
