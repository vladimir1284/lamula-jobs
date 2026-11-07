"""Solicitudes de acceso (D20): alta pública, aprobación o rechazo por el dueño, y envío del token."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone

import psycopg

from .ids import sha256, ulid
from .mail import EnvioFallido, Mailer

INTERESES = ("huracan", "dia", "propias", "otra")
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
MAX_POR_IP_DIA = 5
VIDA_ENLACE = timedelta(days=7)
NIVELES_A_TERCEROS = ("demo", "extendido", "evaluacion")  # `interno` y `casos` nunca se emiten a un solicitante


class SolicitudInvalida(ValueError):
    pass


class Demasiadas(Exception):
    pass


class NoResoluble(Exception):
    """No existe, caducó el enlace o ya está resuelta."""


def _txt(v: str | None, n: int) -> str | None:
    v = (v or "").strip()
    return v[:n] or None


def crear(conn: psycopg.Connection, *, email: str, org: str, cargo: str | None, interes: list[str], radar: str | None,
          comentario: str | None, ip: str | None) -> tuple[str, str]:
    """Guarda una solicitud pendiente. Devuelve (id, enlace secreto de revisión)."""
    email = (email or "").strip()
    org = _txt(org, 200)
    if not EMAIL.match(email):
        raise SolicitudInvalida("correo no válido")
    if not org:
        raise SolicitudInvalida("falta la organización")
    interes = sorted(set(interes or []))
    if not interes or any(i not in INTERESES for i in interes):
        raise SolicitudInvalida("elige qué quieres ver")
    ip_h = sha256(ip) if ip else None
    if ip_h and conn.execute("SELECT count(*) AS n FROM control.access_requests WHERE ip_sha256 = %s AND created_at > now() - interval '1 day'",
                             (ip_h,)).fetchone()["n"] >= MAX_POR_IP_DIA:
        raise Demasiadas("demasiadas solicitudes desde esta red")
    rid, enlace = ulid(), "lmq_" + secrets.token_urlsafe(32)
    try:
        conn.execute(
            """INSERT INTO control.access_requests (id, email, org, cargo, interes, radar, comentario, ip_sha256, review_sha256, review_expires_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (rid, email, org, _txt(cargo, 120), interes, _txt(radar, 120), _txt(comentario, 2000), ip_h, sha256(enlace),
             datetime.now(timezone.utc) + VIDA_ENLACE))
    except psycopg.errors.UniqueViolation:
        raise Demasiadas("ya hay una solicitud pendiente con este correo")
    return rid, enlace


def avisar_al_dueno(conn: psycopg.Connection, mailer: Mailer, *, rid: str, enlace: str, admin_email: str, base_url: str) -> bool:
    s = conn.execute("SELECT * FROM control.access_requests WHERE id = %s", (rid,)).fetchone()
    texto = (f"Solicitud de acceso al demo de LAMULA\n\nCorreo: {s['email']}\nOrganización: {s['org']}\nCargo: {s['cargo'] or '-'}\n"
             f"Quiere ver: {', '.join(s['interes'])}\nRadar o zona: {s['radar'] or '-'}\n\nComentario:\n{s['comentario'] or '-'}\n\n"
             f"Revisar (aprobar o rechazar, con confirmación; caduca en 7 días):\n{base_url.rstrip('/')}/v1/requests/{enlace}/review\n\n"
             f"Por terminal: jobs-admin approve {rid} --tier demo\n")
    try:
        mailer.enviar(admin_email, f"[LAMULA demo] Solicitud de {s['org']}", texto, responder_a=s["email"])
    except EnvioFallido:
        return False
    conn.execute("UPDATE control.access_requests SET notified_at = now() WHERE id = %s", (rid,))
    return True


def por_enlace(conn: psycopg.Connection, enlace: str) -> dict:
    """Solicitud pendiente cuyo enlace sigue vigente."""
    s = conn.execute("SELECT * FROM control.access_requests WHERE review_sha256 = %s", (sha256(enlace),)).fetchone()
    if s is None or s["state"] != "pending" or s["review_expires_at"] < datetime.now(timezone.utc):
        raise NoResoluble("no existe, caducó o ya está resuelta")
    return s


def _pendiente_bloqueada(conn: psycopg.Connection, rid: str) -> dict:
    s = conn.execute("SELECT * FROM control.access_requests WHERE id = %s FOR UPDATE", (rid,)).fetchone()
    if s is None or s["state"] != "pending":
        raise NoResoluble("no existe o ya está resuelta")
    return s


def aprobar(conn: psycopg.Connection, rid: str, *, tier: str, mailer: Mailer, demo_url: str) -> str:
    """Emite el token y se lo manda al solicitante. Si el envío falla no queda nada: el token no existe y sigue pendiente."""
    from .admin import emitir
    if tier not in NIVELES_A_TERCEROS:
        raise SolicitudInvalida(f"nivel no concedible: {tier} (los hay: {', '.join(NIVELES_A_TERCEROS)})")
    with conn.transaction():
        s = _pendiente_bloqueada(conn, rid)
        tid, tok = emitir(conn, email=s["email"], tier=tier, org=s["org"], note=f"solicitud {rid}: {', '.join(s['interes'])}")
        lim = conn.execute("SELECT * FROM control.tiers WHERE name = %s", (tier,)).fetchone()
        conn.execute("UPDATE control.access_requests SET state='approved', resolved_at=now(), token_id=%s WHERE id=%s", (tid, rid))
        mailer.enviar(s["email"], "Su acceso al demo de LAMULA", _correo_token(tok, lim, demo_url))
    return tid


def rechazar(conn: psycopg.Connection, rid: str, *, avisar: bool, mailer: Mailer) -> None:
    with conn.transaction():
        s = _pendiente_bloqueada(conn, rid)
        conn.execute("UPDATE control.access_requests SET state='rejected', resolved_at=now() WHERE id=%s", (rid,))
        if avisar:
            mailer.enviar(s["email"], "Su solicitud de acceso al demo de LAMULA",
                          "Gracias por su interés en el demo de LAMULA. Por ahora no podemos concederle acceso.\n"
                          "Si cree que es un error o su caso ha cambiado, responda a este correo.\n")


def _correo_token(tok: str, lim: dict, demo_url: str) -> str:
    vol = lim["max_volumes"] or "sin tope de"
    jobs = lim["max_jobs_total"] or "sin tope de"
    return (f"Aquí tiene su acceso al demo de LAMULA: {demo_url}\n\n"
            f"El código es {tok} y se pega una sola vez; el navegador lo recuerda. Guárdelo: no podemos recuperarlo, "
            f"aunque sí emitirle otro.\n\n"
            f"Su nivel de acceso permite {vol} volúmenes por trabajo y {jobs} trabajos. Cada trabajo tarda "
            f"aproximadamente lo mismo que duró la tormenta que elija, y no hace falta esperar a que termine: el enlace "
            f"del resultado funciona desde el primer minuto y la línea de tiempo se va llenando sola.\n\n"
            f"Los productos generados son para evaluación: no son productos oficiales de ningún servicio meteorológico.\n\n"
            f"Si necesita más, responda a este correo y lo hablamos.\n")


def pendientes(conn: psycopg.Connection) -> list[dict]:
    return conn.execute("SELECT id, email, org, cargo, interes, radar, created_at, notified_at, review_expires_at "
                        "FROM control.access_requests WHERE state = 'pending' ORDER BY created_at").fetchall()
