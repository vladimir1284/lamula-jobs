"""Configuración por entorno. Nada tiene valor por defecto que sirva en producción."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


def env(name: str, default: str | None = None) -> str:
    v = os.environ.get(name, default)
    if v is None or v == "":
        raise ConfigError(f"falta la variable de entorno {name}")
    return v


@dataclass(frozen=True)
class Secrets:
    """Las contraseñas de los roles de un job se derivan, no se guardan (tenancy.password).

    Dos claves distintas a propósito: el runner conoce RW (publica) y no RO (lo que ve el viewer).
    """

    rw: bytes
    ro: bytes
    result: bytes  # deriva el token de resultado de un job

    @classmethod
    def from_env(cls) -> "Secrets":
        return cls(env("JOBS_RW_SECRET").encode(), env("JOBS_RO_SECRET").encode(), env("JOBS_RESULT_SECRET").encode())
