"""Ayudas para las pruebas de extremo a extremo de F2 (necesitan el entorno de `prepare.py` y el contenedor `job-f2`)."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request

import boto3
import psycopg
from psycopg.rows import dict_row

API = "http://127.0.0.1:58000"
CONTENEDOR = "job-f2"


def api(metodo: str, ruta: str, token: str, cuerpo: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(API + ruta, method=metodo, data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def admin_db() -> psycopg.Connection:
    return psycopg.connect(os.environ["JOBS_ADMIN_DSN"], autocommit=True, row_factory=dict_row)


def s3():
    return boto3.client("s3", endpoint_url="http://127.0.0.1:55000", aws_access_key_id="dev", aws_secret_access_key="dev", region_name="us-east-1")


def claves(bucket: str) -> set[str]:
    out, tok = set(), None
    while True:
        r = s3().list_objects_v2(Bucket=bucket, **({"ContinuationToken": tok} if tok else {}))
        out |= {o["Key"] for o in r.get("Contents", [])}
        tok = r.get("NextContinuationToken")
        if not tok:
            return out


def en_contenedor(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "exec", CONTENEDOR, *cmd], capture_output=True, text=True)


def procesos(nombre: str) -> int:
    return len([x for x in en_contenedor("pgrep", "-x", nombre).stdout.split() if x])


def worker_vivo() -> bool:
    return bool(en_contenedor("bash", "-c", "pgrep -f '[l]amula_jobs.worker'").stdout.strip())


def lanzar_worker(metricas: str = "/data/wear-f2.jsonl", log: str = "/data/worker-f2.log") -> None:
    if not worker_vivo():
        subprocess.run(["docker", "exec", "-d", CONTENEDOR, "bash", "-lc", f"jobs-worker --metricas {metricas} >> {log} 2>&1"], check=True)


def esperar(db: psycopg.Connection, job_id: str, estados: set[str], timeout: float, cada: float = 5.0) -> str:
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        s = db.execute("SELECT state FROM control.jobs WHERE id=%s", (job_id,)).fetchone()["state"]
        if s in estados:
            return s
        time.sleep(cada)
    raise TimeoutError(f"{job_id}: no llegó a {estados} en {timeout:.0f} s (estado {s})")


def alta(token: str, icao: str, claves_staging: list[tuple[str, int]]) -> dict:
    code, j = api("POST", "/v1/jobs", token, {"icao": icao, "inputs": [{"staging_key": k, "bytes": b} for k, b in claves_staging]})
    assert code == 201, (code, j)
    return j


def barrer() -> dict:
    from lamula_jobs import sweep
    from pathlib import Path
    with admin_db() as c:
        return sweep.barrer(c, _almacen(), migraciones=Path(os.environ["PIPELINE_MIGRATIONS"]),
                            rw=os.environ["JOBS_RW_SECRET"].encode(), ro=os.environ["JOBS_RO_SECRET"].encode())


def _almacen():
    from lamula_jobs import sweep
    return sweep.Almacen(s3(), "lamula-demo-raster", "lamula-demo-staging")


def huerfanos() -> dict:
    from lamula_jobs import sweep
    with admin_db() as c:
        return sweep.huerfanos(c)


def subir(local: str, bucket: str = "lamula-demo-staging") -> tuple[str, int]:
    """Copia un volumen a staging bajo un prefijo propio del job: el barrido borra el staging de un job caducado."""
    from lamula_jobs.ids import ulid
    from pathlib import Path
    p = Path(local)
    clave = f"staging/{ulid()}/{p.name}"
    s3().upload_file(str(p), bucket, clave)
    return clave, p.stat().st_size
