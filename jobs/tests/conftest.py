"""Fixtures: una base nueva por sesión en el Postgres de F2 (`lamula-pg-f2`, puerto 55432)."""

from __future__ import annotations

import os
import secrets as sec
from pathlib import Path

import boto3
import psycopg
import pytest
from moto import mock_aws
from psycopg.rows import dict_row

from lamula_jobs import sweep
from lamula_jobs.admin import emitir
from lamula_jobs.config import Secrets
from lamula_jobs.db import migrar

HOST = os.environ.get("TEST_PG_HOST", "127.0.0.1")
PORT = os.environ.get("TEST_PG_PORT", "55432")
ADMIN_PW = os.environ.get("TEST_PG_PASSWORD", "f2-dev-only")
MIGRACIONES = Path(os.environ.get("PIPELINE_MIGRATIONS", Path(__file__).resolve().parents[3] / "nexrad-l3-pipeline/db/pg_migrations"))
SECRETS = Secrets(b"rw-test", b"ro-test", b"res-test")


def dsn(db: str, user: str = "postgres", pw: str = ADMIN_PW) -> str:
    return f"host={HOST} port={PORT} dbname={db} user={user} password={pw}"


@pytest.fixture(scope="session")
def basedatos():
    nombre = "jobs_test_" + sec.token_hex(4)
    with psycopg.connect(dsn("postgres"), autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{nombre}"')
    with psycopg.connect(dsn("postgres"), autocommit=True) as c:
        previos = {r[0] for r in c.execute("SELECT rolname FROM pg_roles WHERE rolname LIKE 'job\\_%'").fetchall()}
    with psycopg.connect(dsn(nombre), autocommit=True, row_factory=dict_row) as c:
        migrar(c)
        c.execute("ALTER ROLE jobs_api LOGIN PASSWORD 'api-pw'")
        c.execute("ALTER ROLE jobs_runner LOGIN PASSWORD 'runner-pw'")
    yield nombre
    with psycopg.connect(dsn("postgres"), autocommit=True) as c:
        c.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (nombre,))
        c.execute(f'DROP DATABASE "{nombre}"')
        # Los roles son del clúster, no de la base: DROP DATABASE no se los lleva. Se borran solo los de
        # job que NO existían al empezar la sesión (los de otras bases del mismo Postgres, p. ej. los de
        # la prueba de extremo a extremo, no son nuestros). Los de servicio se quedan.
        for (r,) in c.execute("SELECT rolname FROM pg_roles WHERE rolname LIKE 'job\\_%'").fetchall():
            if r not in previos:
                c.execute(f'DROP ROLE "{r}"')


@pytest.fixture
def admin(basedatos):
    with psycopg.connect(dsn(basedatos), autocommit=True, row_factory=dict_row) as c:
        yield c


@pytest.fixture
def api_conn(basedatos):
    """Conexión con el rol real de jobs-api: lo que en producción corre, no un superusuario."""
    with psycopg.connect(dsn(basedatos, "jobs_api", "api-pw"), autocommit=True, row_factory=dict_row) as c:
        yield c


@pytest.fixture
def runner_conn(basedatos):
    with psycopg.connect(dsn(basedatos, "jobs_runner", "runner-pw"), autocommit=True, row_factory=dict_row) as c:
        yield c


@pytest.fixture
def almacen():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="cogs")
        s3.create_bucket(Bucket="staging")
        yield sweep.Almacen(s3, "cogs", "staging")


@pytest.fixture
def token(admin, request):
    """Token de nivel `evaluacion` (48 volúmenes, 10 jobs, 2 activos) o el que pida `param`.

    `amplio` es un nivel solo de pruebas, sin topes, para los tests que necesitan muchos jobs a la vez.
    """
    tier = getattr(request, "param", "evaluacion")
    admin.execute("INSERT INTO control.tiers VALUES ('amplio', NULL, NULL, 50, 1, 0, NULL) ON CONFLICT DO NOTHING")
    tid, tok = emitir(admin, email=f"{sec.token_hex(3)}@test", tier=tier)
    yield {"id": tid, "token": tok}


_dias = iter(range(20100101, 20991231))
_n = [0]


def dia_unico() -> str:
    """Un día distinto por llamada: el guardián de solapado vale para toda la base de la sesión."""
    _n[0] += 1
    return f"{2000 + _n[0] // 360:04d}{(_n[0] % 360) // 30 + 1:02d}{_n[0] % 30 + 1:02d}"


def claves(icao: str, dia: str, n: int, *, minuto0: int = 0) -> list[str]:
    return [f"staging/x/{icao}{dia}_{(minuto0 + 5 * i) // 60:02d}{(minuto0 + 5 * i) % 60:02d}00_V06" for i in range(n)]
