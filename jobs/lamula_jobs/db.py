"""Conexión y migración del schema de control."""

from __future__ import annotations

from pathlib import Path

import psycopg
from psycopg.rows import dict_row

MIGRACIONES = Path(__file__).parent / "migrations"


def conectar(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn, row_factory=dict_row, autocommit=True)


def migrar(conn: psycopg.Connection) -> list[str]:
    """Aplica en orden las migraciones de control que falten. Devuelve las aplicadas."""
    conn.execute("CREATE SCHEMA IF NOT EXISTS control")
    conn.execute("CREATE TABLE IF NOT EXISTS control.schema_migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
    hechas = {r["name"] for r in conn.execute("SELECT name FROM control.schema_migrations")}
    nuevas = []
    for f in sorted(MIGRACIONES.glob("*.sql")):
        if f.name in hechas:
            continue
        with conn.transaction():
            conn.execute(f.read_text())
            conn.execute("INSERT INTO control.schema_migrations (name) VALUES (%s)", (f.name,))
        nuevas.append(f.name)
    return nuevas
