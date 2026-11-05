"""Schema y roles por job (D4): `job_<id>` con las migraciones del pipeline tal cual.

Dos roles por job: `job_<id>` (escribe: el runner) y `job_<id>_ro` (lee: el viewer), cada uno con
`search_path` fijo al schema. Las tablas pertenecen a quien ejecuta esto (el rol de jobs-api), no
al rol del job: un job comprometido no puede alterar la forma de su schema.
"""

from __future__ import annotations

import re
from pathlib import Path

import psycopg
from psycopg import sql

from .ids import derivar

_ID = re.compile(r"^[0-9a-hjkmnp-tv-z]{26}$")


def _check(job_id: str) -> str:
    if not _ID.match(job_id):
        raise ValueError(f"id de job no válido: {job_id!r}")  # va a SQL como identificador
    return job_id


def schema_de(job_id: str) -> str:
    return f"job_{_check(job_id)}"


def rol_rw(job_id: str) -> str:
    return schema_de(job_id)


def rol_ro(job_id: str) -> str:
    return schema_de(job_id) + "_ro"


def password(clave: bytes, rol: str, job_id: str) -> str:
    return derivar(clave, rol, _check(job_id))[:48]


def _existe_rol(conn: psycopg.Connection, nombre: str) -> bool:
    return conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (nombre,)).fetchone() is not None


def crear(conn: psycopg.Connection, job_id: str, *, migraciones: Path, rw_secret: bytes, ro_secret: bytes) -> None:
    """Crea schema, roles y aplica TODAS las migraciones del pipeline (también la del mosaico).

    Idempotente solo en el sentido de «falla limpio»: si algo sale mal a medias, deja el estado
    para que `borrar` lo recoja, que es lo que hace el barrido.
    """
    sch, rw, ro = schema_de(job_id), rol_rw(job_id), rol_ro(job_id)
    S, RW, RO = sql.Identifier(sch), sql.Identifier(rw), sql.Identifier(ro)
    ficheros = sorted(migraciones.glob("*.sql"))
    if not ficheros:
        raise FileNotFoundError(f"sin migraciones en {migraciones}")
    for nombre, pw in ((rw, password(rw_secret, "rw", job_id)), (ro, password(ro_secret, "ro", job_id))):
        if _existe_rol(conn, nombre):
            raise RuntimeError(f"el rol {nombre} ya existe")
        conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE CONNECTION LIMIT 8").format(sql.Identifier(nombre), sql.Literal(pw)))
    conn.execute(sql.SQL("CREATE SCHEMA {}").format(S))
    conn.execute(sql.SQL("ALTER ROLE {} SET search_path = {}").format(RW, S))
    conn.execute(sql.SQL("ALTER ROLE {} SET search_path = {}").format(RO, S))
    with conn.transaction():
        conn.execute(sql.SQL("SET LOCAL search_path = {}").format(S))
        for f in ficheros:
            conn.execute(f.read_text())
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}, {}").format(S, RW, RO))
        conn.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}").format(S, RW))
        conn.execute(sql.SQL("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA {} TO {}").format(S, RW))
        conn.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(S, RO))


def claves_r2(conn: psycopg.Connection, job_id: str) -> list[str]:
    """Las claves de objeto que el job escribió, leídas de su schema antes de borrarlo."""
    S = sql.Identifier(schema_de(job_id))
    if conn.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (schema_de(job_id),)).fetchone() is None:
        return []
    claves: list[str] = []
    for tabla in ("rasters", "mosaic_rasters"):
        if conn.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s", (schema_de(job_id), tabla)).fetchone():
            claves += [r["r2_key"] for r in conn.execute(sql.SQL("SELECT r2_key FROM {}.{}").format(S, sql.Identifier(tabla)))]
    return claves


def borrar(conn: psycopg.Connection, job_id: str) -> None:
    """DROP SCHEMA CASCADE y los dos roles. Cierra antes las conexiones vivas de esos roles."""
    sch, rw, ro = schema_de(job_id), rol_rw(job_id), rol_ro(job_id)
    for r in (rw, ro):
        conn.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = %s", (r,))
    conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(sch)))
    for r in (rw, ro):
        # Los roles no son dueños de nada (las tablas son de jobs-api) y sus permisos se fueron con el
        # schema, así que DROP ROLE no necesita DROP OWNED (que en PG16 exige pertenecer al rol).
        if _existe_rol(conn, r):
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(r)))


def huerfanos(conn: psycopg.Connection, vivos: set[str]) -> dict[str, list[str]]:
    """Schemas y roles `job_*` de la base que no corresponden a ningún job vigente."""
    esquemas = [r["nspname"] for r in conn.execute("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'job\\_%'")]
    roles = [r["rolname"] for r in conn.execute("SELECT rolname FROM pg_roles WHERE rolname LIKE 'job\\_%'")]

    def raiz(n: str) -> str:
        return n.removeprefix("job_").removesuffix("_ro")

    return {"schemas": [s for s in esquemas if raiz(s) not in vivos], "roles": [r for r in roles if raiz(r) not in vivos]}
