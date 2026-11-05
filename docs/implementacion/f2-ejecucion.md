# F2 en una máquina con Docker

Comandos literales, en orden, de lo que se ejecutó el 2026-11-04 para cerrar F2. Sin Swarm, sin R2
y sin el Postgres de producción: Postgres desechable y un S3 simulado con
[moto](https://github.com/getmoto/moto). Los resultados están en
[Resultados de F2](../referencia/f2-resultados.md).

!!! warning "Entorno de desarrollo"
    Las contraseñas de abajo (`f2-dev-only`, `api-pw`, `runner-pw`, `dev-*`) son de esta prueba y no
    sirven para nada más. Las de producción las pone el despliegue.

## 1. Postgres y red

```bash
docker network create lamula-f2
docker run -d --name lamula-pg-f2 --restart no -e POSTGRES_PASSWORD=f2-dev-only -e POSTGRES_DB=lamula_demo \
  -p 127.0.0.1:55432:5432 -v lamula-pg-f2-data:/var/lib/postgresql/data \
  postgres:16-alpine -c max_connections=200
docker network connect lamula-f2 lamula-pg-f2
```

Es un Postgres propio de F2: **no** es el Supabase que había en la máquina ni el de producción.

## 2. Pruebas unitarias y de integración (sin ORPG)

```bash
cd jobs && uv sync && uv run pytest -q          # 26 pruebas contra el Postgres del paso 1
```

Cada sesión crea y borra su propia base (`jobs_test_*`), así que se pueden lanzar con el entorno
de los pasos siguientes en marcha.

## 3. Almacén S3 simulado y datos

```bash
cd jobs && nohup uv run moto_server -H 0.0.0.0 -p 55000 > moto.log 2>&1 &
uv run python e2e/prepare.py --env f2.env  /ruta/a/KAMX20170910_170248_V06  /ruta/a/KHGX20261101_162110_V06
```

`prepare.py` aplica las migraciones de control, pone contraseña a `jobs_api` y `jobs_runner`, crea los
buckets `lamula-demo-raster` y `lamula-demo-staging` y escribe `f2.env`. El contenedor ve el S3 del
host por la puerta de enlace de la red (`172.20.0.1` aquí; `docker network inspect lamula-f2`).

!!! note "Cargar `f2.env` en la shell"
    Los DSN llevan espacios; no vale `source`. Línea a línea:
    `while IFS= read -r l; do [ -n "$l" ] && export "$l"; done < f2.env`.

## 4. API y token

```bash
nohup uvicorn --factory lamula_jobs.api:create_app --host 127.0.0.1 --port 58000 > api.log 2>&1 &
jobs-admin issue --email yo@ejemplo --tier interno --note "e2e"      # el token se muestra una sola vez
```

## 5. El runner

```bash
docker build -f job-runner/Dockerfile --build-context pipeline=../nexrad-l3-pipeline -t job-runner:f2 .
docker run -d --name job-f2 --hostname orpg-job --network lamula-f2 --stop-timeout 60 \
  --env-file f2.env -v "$PWD/f0-run:/data" job-runner:f2
docker exec -d job-f2 bash -lc 'jobs-supervisor --metricas /data/wear-f2.jsonl >> /data/worker-f2.log 2>&1'
```

!!! danger "El `ENTRYPOINT` de la imagen ignora el comando"
    `entrypoint.sh` (heredado del ORPG de producción) arranca `mrpg` y se queda en `sleep infinity`; **no
    ejecuta el `CMD`**. Pasar `bash -lc jobs-worker` a `docker run` no lanza nada y el job se queda en
    la cola sin ningún error (se perdieron 20 minutos de esta manera). El worker se lanza con
    `docker exec`, como en F1.

**Supervisión (2026-11-05).** `jobs-supervisor` (`job-runner/supervisor.sh`) envuelve al worker: si
sale, lo relanza con pausa creciente (2 s, 4 s … máx. 60 s; vuelve a 2 s si el worker aguantó ≥60 s) y
reenvía SIGTERM, tanto en la pausa como con un job en curso. Probado con un worker falso que muere cada
segundo, y **con el ORPG real** (2026-11-05, `jobs/e2e/muerte_worker.py`): `kill -9` al worker con
`play_a2` reproduciendo → worker nuevo a los 2 s → el barrido (timeout 40 s en la prueba; 600 s en
producción) devuelve el job a la cola → el worker nuevo lo termina `ready` en el intento 2, sin procesos
del ORPG, schemas ni roles huérfanos. Un job que se queda a medias lo recoge el barrido, no el
supervisor. Observado: el ORPG del worker muerto sigue reproduciendo hasta que el worker nuevo reclama
el job y llama a `limpiar_orpg` (con el timeout de producción, hasta ~10 min con el ORPG ocupado).

**Alarma de cola y barrido.** Se programan fuera del contenedor del runner:

```bash
jobs-admin health            # sale con 1 si hay jobs en cola >300 s o en marcha sin latido >300 s
jobs-admin sweep --cada 60   # el barrido en bucle, como servicio; sin --cada, una vez
```

`health` está pensada para un chequeo periódico (cron, o el healthcheck de un servicio) que avise al
dueño; qué canal de aviso se usa sigue abierto.

## 6. Las puertas

```bash
PYTHONPATH=e2e python e2e/gate.py  token.txt          # cancelación a mitad + dos jobs seguidos, ~25 min
PYTHONPATH=e2e python e2e/desgaste.py token.txt 12    # tanda de desgaste, ~2 h
```

Los dos suponen los pasos 1 a 5. `lib.subir` copia cada volumen a staging bajo un prefijo propio del
job: el barrido borra el staging de un job caducado, así que dos jobs no deben compartir claves.

## Limpieza

```bash
docker rm -f job-f2 lamula-pg-f2 && docker volume rm lamula-pg-f2-data && docker network rm lamula-f2
kill $(cat api.pid)        # y el proceso de moto_server; por PID, nunca por patrón
```
