# Imagen de jobs-api y de jobs-admin (barrido, alarma, casos, aprobaciones). SIN ORPG: es lo único público.
#
#   docker build -f jobs/Dockerfile --build-context pipeline=../nexrad-l3-pipeline -t jobs-api:TAG jobs
#
# El contexto de construcción es `jobs/`; las migraciones del pipeline entran por el contexto nombrado
# `pipeline` (solo `db/pg_migrations`): `tenancy.py` las aplica tal cual en el schema de cada job.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1 PIPELINE_MIGRATIONS=/opt/pipeline/db/pg_migrations
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY lamula_jobs lamula_jobs
RUN uv sync --frozen --no-dev
COPY --from=pipeline db/pg_migrations /opt/pipeline/db/pg_migrations
ENV PATH=/app/.venv/bin:$PATH
RUN useradd -r -u 10001 jobs
USER jobs
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=4).status==200 else 1)"
CMD ["uvicorn", "--factory", "lamula_jobs.api:create_app", "--host", "0.0.0.0", "--port", "8000"]
