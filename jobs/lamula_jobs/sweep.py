"""Barrido: lo que ni la API ni el runner hacen en línea.

1. Devuelve a la cola los jobs de runners muertos (y rehace su schema desde cero).
2. Caduca los jobs vencidos.
3. Borra schema, roles, objetos del bucket y staging de lo cancelado o caducado.

Es idempotente y se puede lanzar en bucle o a mano (`jobs-admin sweep`). Corre con el rol de
jobs-api, que es el único con permiso para crear y borrar schemas y roles.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import psycopg

from . import queue, tenancy

log = logging.getLogger("lamula_jobs.sweep")


@dataclass
class Almacen:
    """Lo que el barrido necesita del almacén de objetos: un cliente S3 y los dos buckets."""

    s3: object
    bucket: str          # COGs de los jobs (lamula-demo-raster)
    staging_bucket: str  # volúmenes Level II

    def borrar(self, bucket: str, claves: list[str]) -> int:
        n = 0
        for i in range(0, len(claves), 1000):
            lote = claves[i:i + 1000]
            self.s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in lote], "Quiet": True})
            n += len(lote)
        return n


def borrar_recursos(conn: psycopg.Connection, almacen: Almacen, job_id: str, *, staging: bool) -> dict:
    claves = tenancy.claves_r2(conn, job_id)
    out = {"cogs": almacen.borrar(almacen.bucket, claves) if claves else 0, "staging": 0}
    if staging:
        ks = [r["staging_key"] for r in queue.entradas_de(conn, job_id)]
        out["staging"] = almacen.borrar(almacen.staging_bucket, ks) if ks else 0
    tenancy.borrar(conn, job_id)
    conn.execute("UPDATE control.jobs SET resources_dropped_at = now() WHERE id = %s", (job_id,))
    return out


def resetear(conn: psycopg.Connection, almacen: Almacen, job_id: str, *, migraciones: Path, rw: bytes, ro: bytes) -> None:
    """Schema nuevo y vacío para un reintento. Los objetos del intento anterior se borran: son del mismo job."""
    borrar_recursos(conn, almacen, job_id, staging=False)
    conn.execute("UPDATE control.jobs SET resources_dropped_at = NULL WHERE id = %s", (job_id,))
    tenancy.crear(conn, job_id, migraciones=migraciones, rw_secret=rw, ro_secret=ro)


def barrer(conn: psycopg.Connection, almacen: Almacen, *, migraciones: Path, rw: bytes, ro: bytes, timeout_s: int = 600) -> dict:
    res = {"requeued": [], "failed": [], "dropped": []}
    for j in queue.reclamar_muertos(conn, timeout_s=timeout_s):
        if j["state"] == "queued":
            resetear(conn, almacen, j["id"], migraciones=migraciones, rw=rw, ro=ro)
            res["requeued"].append(j["id"])
        else:
            res["failed"].append(j["id"])
    # un alta que murió entre la fila y el schema: no puede quedarse en la cola ni contar como activo
    conn.execute("UPDATE control.jobs SET state = 'failed', error = 'alta incompleta', finished_at = now() WHERE state = 'creating' AND created_at < now() - interval '10 minutes'")
    conn.execute("UPDATE control.jobs SET state = 'expired' WHERE state IN ('ready','failed') AND expires_at < now()")
    # cancelado y caducado: fuera todo ya. Fallido: se conserva hasta caducar, para depurar.
    for j in conn.execute("SELECT id, state FROM control.jobs WHERE state IN ('cancelled','expired') AND resources_dropped_at IS NULL").fetchall():
        borrar_recursos(conn, almacen, j["id"], staging=True)
        res["dropped"].append(j["id"])
    return res


def salud(conn: psycopg.Connection, *, cola_max_s: int = 300, latido_max_s: int = 300) -> dict[str, list[dict]]:
    """La alarma de la cola: lo que debería haberse movido y no se mueve. Vacío = sano.

    - `sin_reclamar`: jobs `queued` más viejos de `cola_max_s`. Es la señal de que no hay worker vivo
      (o de que ninguno puede tomarlos); sin esta comprobación un job así espera para siempre sin error.
    - `latido_viejo`: jobs reclamados cuyo latido pasó de `latido_max_s`. El barrido los recoge al
      llegar a su `timeout_s`; esto avisa antes, o avisa de que el barrido no corre.
    """
    cols = "id, icao, state, created_at, heartbeat_at, attempts"
    return {
        "sin_reclamar": conn.execute(
            f"SELECT {cols} FROM control.jobs WHERE state = 'queued' AND NOT cancel_requested "
            "AND created_at < now() - make_interval(secs => %s) ORDER BY created_at", (cola_max_s,)).fetchall(),
        "latido_viejo": conn.execute(
            f"SELECT {cols} FROM control.jobs WHERE state IN ('claimed','ingesting') "
            "AND heartbeat_at < now() - make_interval(secs => %s) ORDER BY heartbeat_at", (latido_max_s,)).fetchall(),
    }


def huerfanos(conn: psycopg.Connection) -> dict[str, list[str]]:
    """Schemas y roles job_* sin job vigente (con recursos aún sin borrar). Debería salir siempre vacío."""
    vivos = {r["id"] for r in conn.execute("SELECT id FROM control.jobs WHERE resources_dropped_at IS NULL")}
    return tenancy.huerfanos(conn, vivos)
