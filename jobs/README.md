# lamula-jobs (F2)

Servicio de jobs del demo: `jobs-api` (FastAPI), cola en Postgres, tenencia por job (un schema y dos roles,
D4), barrido, `jobs-admin` y el bucle del runner (`jobs-worker`, dentro de la imagen `job-runner`).

- `lamula_jobs/migrations/` — schema `control` y roles de servicio. **No** toca el contrato del pipeline.
- `lamula_jobs/tenancy.py` — crea y borra `job_<id>` aplicando las migraciones de `nexrad-l3-pipeline` tal cual.
- `lamula_jobs/queue.py` — alta con cuotas, `FOR UPDATE SKIP LOCKED`, latido, cancelación.
- `lamula_jobs/sweep.py` — runners muertos, caducidad, borrado de schema, roles y objetos.
- `lamula_jobs/worker.py` — ejecuta un job entero (stdlib + psycopg + boto3; no importa FastAPI).
- `e2e/` — preparación y puertas con el ORPG real. Runbook: `docs/implementacion/f2-ejecucion.md`.

```bash
uv sync && uv run pytest -q     # necesita el Postgres de F2 en 127.0.0.1:55432 (ver el runbook)
```
