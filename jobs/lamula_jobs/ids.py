"""ULID en minúsculas (válido como identificador de Postgres sin comillas) y tokens."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

_ALFABETO = "0123456789abcdefghjkmnpqrstvwxyz"  # Crockford, minúsculas


def ulid() -> str:
    n = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    return "".join(_ALFABETO[(n >> s) & 31] for s in range(125, -1, -5))


def sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def nuevo_token_acceso() -> str:
    return "lma_" + secrets.token_urlsafe(32)


def derivar(clave: bytes, etiqueta: str, job_id: str) -> str:
    return hmac.new(clave, f"{etiqueta}:{job_id}".encode(), hashlib.sha256).hexdigest()


def token_resultado(clave: bytes, job_id: str) -> str:
    """Determinista: quien tiene el token de acceso puede volver a pedir el enlace sin que lo guardemos."""
    return "lmr_" + derivar(clave, "result", job_id)[:43]
