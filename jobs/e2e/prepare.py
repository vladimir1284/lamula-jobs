"""Prepara el entorno de pruebas de extremo a extremo de F2 (solo desarrollo).

Postgres: `lamula-pg-f2`. Almacén S3: moto en el host (no hay credenciales de R2 y el bucket demo no
existe todavía). Sube a staging los volúmenes que se le pasen y escribe un fichero de entorno.

    uv run python e2e/prepare.py --env f2.env /ruta/KAMX2017...  /ruta/KHGX2026...
"""

from __future__ import annotations

import argparse
from pathlib import Path

import boto3
import psycopg
from psycopg.rows import dict_row

from lamula_jobs.db import migrar

PG_HOST_LOCAL, PG_PORT_LOCAL = "127.0.0.1", 55432
S3_LOCAL = "http://127.0.0.1:55000"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True, type=Path)
    ap.add_argument("--s3-container", default="http://172.20.0.1:55000", help="cómo ve el contenedor el almacén S3")
    ap.add_argument("volumenes", nargs="*", type=Path)
    a = ap.parse_args()
    with psycopg.connect(f"host={PG_HOST_LOCAL} port={PG_PORT_LOCAL} dbname=lamula_demo user=postgres password=f2-dev-only", autocommit=True, row_factory=dict_row) as c:
        print("migraciones:", migrar(c))
        c.execute("ALTER ROLE jobs_api LOGIN PASSWORD 'api-pw'")
        c.execute("ALTER ROLE jobs_runner LOGIN PASSWORD 'runner-pw'")
    s3 = boto3.client("s3", endpoint_url=S3_LOCAL, aws_access_key_id="dev", aws_secret_access_key="dev", region_name="us-east-1")
    for b in ("lamula-demo-raster", "lamula-demo-staging"):
        try:
            s3.create_bucket(Bucket=b)
        except s3.exceptions.BucketAlreadyOwnedByYou:
            pass
    for v in a.volumenes:
        s3.upload_file(str(v), "lamula-demo-staging", f"staging/{v.name}")
        print("staging/" + v.name, v.stat().st_size)
    a.env.write_text("\n".join([
        "JOBS_RW_SECRET=dev-rw", "JOBS_RO_SECRET=dev-ro", "JOBS_RESULT_SECRET=dev-result", "JOBS_INTERNAL_KEY=dev-internal",
        "PIPELINE_MIGRATIONS=" + str(Path(__file__).resolve().parents[3] / "nexrad-l3-pipeline/db/pg_migrations"),
        "JOBS_ADMIN_DSN=host=127.0.0.1 port=55432 dbname=lamula_demo user=postgres password=f2-dev-only",
        "JOBS_API_DSN=host=127.0.0.1 port=55432 dbname=lamula_demo user=jobs_api password=api-pw",
        "JOBS_RUNNER_DSN=host=lamula-pg-f2 port=5432 dbname=lamula_demo user=jobs_runner password=runner-pw",
        "PG_HOST=lamula-pg-f2", "PG_PORT=5432", "PG_DB=lamula_demo",
        f"R2_ENDPOINT={a.s3_container}", "R2_ACCESS_KEY_ID=dev", "R2_SECRET_ACCESS_KEY=dev",
        "R2_BUCKET=lamula-demo-raster", "STAGING_BUCKET=lamula-demo-staging", ""]))
    print("entorno en", a.env)


if __name__ == "__main__":
    main()
