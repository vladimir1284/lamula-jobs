"""Cola de jobs sobre Postgres: alta con cuotas, `FOR UPDATE SKIP LOCKED`, latido, cancelación y barrido.

Estados: queued → claimed → ingesting → ready, y aparte failed, cancelled y expired.
Todo el estado vive en `control.jobs`; los procesos (API, runner, barrido) no comparten nada más.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import psycopg

from .ids import sha256, ulid

ACTIVOS = ("creating", "queued", "claimed", "ingesting")
VIVOS = ACTIVOS + ("ready",)
MAX_INTENTOS = 2  # docs/arquitectura/ciclo-runner.md: dos intentos fallidos y el job es failed
ICAO = re.compile(r"^[A-Z][A-Z0-9]{3}$")
CLAVE = re.compile(r"(?P<icao>[A-Z][A-Z0-9]{3})(?P<f>\d{8})_(?P<h>\d{6})")


class CuotaExcedida(Exception):
    """El token no puede crear este job; el mensaje dice qué cuota."""


class EntradaInvalida(ValueError):
    pass


class Solapado(Exception):
    """Otro job vivo cubre el mismo radar y las mismas horas (ver `crear`)."""


@dataclass(frozen=True)
class Entrada:
    staging_key: str
    bytes: int = 0
    source_key: str | None = None


def _hora(clave: str, icao: str) -> datetime:
    m = CLAVE.search(clave.rsplit("/", 1)[-1])
    if not m or m["icao"] != icao:
        raise EntradaInvalida(f"{clave}: no es un volumen de {icao} (ICAOyyyymmdd_hhmmss)")
    return datetime.strptime(m["f"] + m["h"], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def validar_token(conn: psycopg.Connection, token: str) -> dict | None:
    """Fila del token con su nivel, o None si no existe, caducó o está revocado."""
    return conn.execute(
        """SELECT t.*, x.max_volumes, x.max_jobs_total, x.max_jobs_active, x.retention_days, x.priority, x.max_bytes
             FROM control.access_tokens t JOIN control.tiers x ON x.name = t.tier
            WHERE t.token_sha256 = %s AND t.revoked_at IS NULL AND (t.expires_at IS NULL OR t.expires_at > now())""",
        (sha256(token),)).fetchone()


def crear(conn: psycopg.Connection, tok: dict, *, icao: str, entradas: list[Entrada], result_token_de, job_id: str | None = None,
          caso: str | None = None) -> dict:
    """Valida cuotas y entradas e inserta el job en `creating` (todavía invisible para los runners).

    `caso` (D19) marca un caso preparado: sin caducidad y con los datos en la base y el bucket de casos, así
    que el solape solo se mira entre casos.

    NO crea el schema: lo hace quien llama, y solo entonces `publicar` lo pasa a `queued`.

    Las cuotas se comprueban dentro de una transacción con el token bloqueado (`FOR UPDATE`), para que
    dos altas simultáneas del mismo token no se cuelen las dos por la última plaza.

    **Solapado.** El pipeline escribe los COG con claves `{site}/{producto}/{fecha}/...` sin nada del
    job, así que dos jobs vivos del mismo radar y las mismas horas se pisarían los objetos en el
    bucket. Hasta que el pipeline admita `R2_KEY_PREFIX` (docs/arquitectura/aislamiento-datos.md) el
    alta se rechaza con `Solapado` en vez de dejar que se corrompan en silencio.
    """
    if not ICAO.match(icao):
        raise EntradaInvalida(f"ICAO no válido: {icao!r}")
    if not entradas:
        raise EntradaInvalida("sin volúmenes")
    horas = [_hora(e.staging_key, icao) for e in entradas]
    if horas != sorted(set(horas)):
        raise EntradaInvalida("los volúmenes tienen que venir en orden cronológico estricto, sin repetir")
    if tok["max_volumes"] is not None and len(entradas) > tok["max_volumes"]:
        raise CuotaExcedida(f"{len(entradas)} volúmenes; el nivel {tok['tier']} permite {tok['max_volumes']}")
    total = sum(e.bytes for e in entradas)
    if tok["max_bytes"] is not None and total > tok["max_bytes"]:
        raise CuotaExcedida(f"{total} B; el nivel {tok['tier']} permite {tok['max_bytes']}")
    jid = job_id or ulid()
    destino = "casos" if caso else "demo"
    ahora = datetime.now(timezone.utc)
    with conn.transaction():
        conn.execute("SELECT 1 FROM control.access_tokens WHERE id = %s FOR UPDATE", (tok["id"],))
        c = conn.execute(
            """SELECT count(*) FILTER (WHERE state NOT IN ('failed','cancelled')) AS total,
                      count(*) FILTER (WHERE state IN ('creating','queued','claimed','ingesting')) AS activos
                 FROM control.jobs WHERE token_id = %s""", (tok["id"],)).fetchone()
        if tok["max_jobs_total"] is not None and c["total"] >= tok["max_jobs_total"]:
            raise CuotaExcedida(f"el nivel {tok['tier']} permite {tok['max_jobs_total']} jobs en total")
        if c["activos"] >= tok["max_jobs_active"]:
            raise CuotaExcedida(f"el nivel {tok['tier']} permite {tok['max_jobs_active']} job(s) activo(s) a la vez")
        choque = conn.execute(
            """SELECT id FROM control.jobs WHERE icao = %s AND state = ANY(%s) AND destino = %s
                  AND vol_from <= %s AND vol_to >= %s LIMIT 1""",
            (icao, list(VIVOS), destino, horas[-1], horas[0])).fetchone()
        if choque:
            raise Solapado(f"el job {choque['id']} ya cubre {icao} en esas horas; dos jobs pisarían los mismos objetos del bucket")
        conn.execute(
            """INSERT INTO control.jobs (id, token_id, state, icao, vol_from, vol_to, n_volumes, total_bytes, priority,
                                         result_token_sha256, expires_at, destino, caso)
               VALUES (%s,%s,'creating',%s,%s,%s,%s,%s,%s,%s, %s, %s, %s)""",
            (jid, tok["id"], icao, horas[0], horas[-1], len(entradas), total, tok["priority"],
             sha256(result_token_de(jid)), None if caso else ahora + timedelta(days=tok["retention_days"]), destino, caso))
        for i, e in enumerate(entradas):
            conn.execute("INSERT INTO control.job_inputs (job_id, seq, staging_key, source_key, bytes) VALUES (%s,%s,%s,%s,%s)",
                         (jid, i, e.staging_key, e.source_key, e.bytes))
    return obtener(conn, jid)


def publicar(conn: psycopg.Connection, job_id: str) -> None:
    conn.execute("UPDATE control.jobs SET state = 'queued' WHERE id = %s AND state = 'creating'", (job_id,))


def obtener(conn: psycopg.Connection, job_id: str) -> dict:
    j = conn.execute("SELECT * FROM control.jobs WHERE id = %s", (job_id,)).fetchone()
    if j is None:
        raise KeyError(job_id)
    return j


def entradas_de(conn: psycopg.Connection, job_id: str) -> list[dict]:
    return conn.execute("SELECT seq, staging_key, source_key, bytes FROM control.job_inputs WHERE job_id = %s ORDER BY seq", (job_id,)).fetchall()


def tomar(conn: psycopg.Connection, runner: str) -> dict | None:
    """Reclama el job más prioritario y antiguo. Dos runners nunca se llevan el mismo."""
    return conn.execute(
        """UPDATE control.jobs SET state = 'claimed', claimed_by = %s, claimed_at = now(), heartbeat_at = now(),
                  attempts = attempts + 1, error = NULL
            WHERE id = (SELECT id FROM control.jobs WHERE state = 'queued' AND NOT cancel_requested
                         ORDER BY priority DESC, created_at LIMIT 1 FOR UPDATE SKIP LOCKED)
        RETURNING *""", (runner,)).fetchone()


def latir(conn: psycopg.Connection, job_id: str, runner: str) -> bool:
    """Marca vida. Devuelve True si hay que cancelar (o si este runner ya no es el dueño del job)."""
    r = conn.execute(
        """UPDATE control.jobs SET heartbeat_at = now() WHERE id = %s AND claimed_by = %s
              AND state IN ('claimed','ingesting') RETURNING cancel_requested""", (job_id, runner)).fetchone()
    return True if r is None else r["cancel_requested"]


def empezar(conn: psycopg.Connection, job_id: str, runner: str) -> None:
    conn.execute("UPDATE control.jobs SET state = 'ingesting', started_at = coalesce(started_at, now()) WHERE id = %s AND claimed_by = %s AND state = 'claimed'",
                 (job_id, runner))


def terminar(conn: psycopg.Connection, job_id: str, runner: str, *, error: str | None = None, cancelado: bool = False) -> None:
    estado = "cancelled" if cancelado else ("failed" if error else "ready")
    conn.execute("UPDATE control.jobs SET state = %s, error = %s, finished_at = now() WHERE id = %s AND claimed_by = %s AND state IN ('claimed','ingesting')",
                 (estado, error, job_id, runner))


def cancelar(conn: psycopg.Connection, job_id: str) -> str:
    """En cola se cancela al instante; en marcha, se pide y el runner lo ve en su próximo latido."""
    with conn.transaction():
        j = conn.execute("SELECT state FROM control.jobs WHERE id = %s FOR UPDATE", (job_id,)).fetchone()
        if j is None:
            raise KeyError(job_id)
        if j["state"] == "queued":
            conn.execute("UPDATE control.jobs SET state = 'cancelled', finished_at = now(), cancel_requested = true WHERE id = %s", (job_id,))
            return "cancelled"
        if j["state"] in ("claimed", "ingesting"):
            conn.execute("UPDATE control.jobs SET cancel_requested = true WHERE id = %s", (job_id,))
            return "cancel_requested"
        return j["state"]  # ya terminó: nada que cancelar


def reclamar_muertos(conn: psycopg.Connection, *, timeout_s: int) -> list[dict]:
    """Un runner muerto deja su job reclamado: vuelve a la cola, o a failed si agotó los intentos.

    El schema del job pasa por `resetear` antes de reintentar (lo hace el barrido, que es quien tiene
    permiso para crear schemas): lo publicado a medias por el intento muerto no debe mezclarse con el
    siguiente.
    """
    return conn.execute(
        """UPDATE control.jobs SET
                  state = CASE WHEN cancel_requested THEN 'cancelled' WHEN attempts >= %s THEN 'failed' ELSE 'queued' END,
                  error = CASE WHEN attempts >= %s AND NOT cancel_requested THEN 'el runner dejó de dar señales de vida' END,
                  finished_at = CASE WHEN cancel_requested OR attempts >= %s THEN now() END,
                  claimed_by = NULL
            WHERE state IN ('claimed','ingesting') AND heartbeat_at < now() - make_interval(secs => %s)
        RETURNING id, state""", (MAX_INTENTOS, MAX_INTENTOS, MAX_INTENTOS, timeout_s)).fetchall()
