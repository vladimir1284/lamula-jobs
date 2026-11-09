# Despliegue en Portainer (Swarm)

Guía para poner el demo en producción: imágenes, bases de datos, buckets, DNS, correo, captcha y la pila
`deploy/lamula-jobs.stack.yml`, que Portainer lee desde git. Está escrita a partir de un ensayo local del camino
completo (2026-11-09); al final hay una tabla de **qué se probó y qué no**. Los pasos están en el orden en que
hay que hacerlos: cada uno deja una comprobación que tiene que pasar antes de seguir.

!!! warning "Lo que no cubre esta guía"
    No se ha probado nada contra Brevo, Turnstile en un navegador real, Cloudflare R2, Traefik ni Portainer. Está
    probado el código y las imágenes contra un Postgres y un S3 locales. Donde la guía dice «debería», es
    inferencia, no medida.

## 1. Qué se despliega

| Servicio | Imagen | Red | Sale a internet |
|---|---|---|---|
| `jobs-api` | `jobs-api` (sin ORPG) | `traefik-public`, `postgres-public`, `jobs-internal` | **Solo** `/v1/public/*` y `/v1/requests/*` |
| `jobs-sweep` | `jobs-api`, otro comando | `postgres-public` | No |
| `jobs-health` | `jobs-api`, otro comando | `postgres-public` | No |
| `jobs-worker` | `job-runner` (**con ORPG, privada**) | `postgres-public` | No |
| `viewer-jobs` | `lamula-webviewer` | `traefik-public`, `postgres-public`, `jobs-internal` | `demo.ladetec.com` (propuesta) |
| `viewer-casos` | `lamula-webviewer`, otra configuración | `traefik-public`, `postgres-public` | `casos.ladetec.com` (propuesta) |

Además, sin servicio propio: dos bases en el Postgres compartido (`lamula_demo`, `lamula_casos`), tres buckets en R2
(rasters de jobs, staging de jobs, rasters de casos) y los hostnames públicos de los dos buckets de rasters.

`jobs-internal` es una red overlay solo para los visores y `jobs-api`. Los visores llaman a `/v1/jobs`,
`/v1/catalog` y `/v1/results` por ahí; **esas rutas no tienen router en Traefik**, que es el filtro de rutas de D20.

Los nombres de host `demo.ladetec.com` y `casos.ladetec.com` son propuesta mía: el dueño del producto solo fijó
`jobs.ladetec.com`. Se cambian con variables, no con código.

## 2. Antes de empezar: lo que tiene que existir

- **Registro de imágenes privado.** El runner contiene código de la Universidad de Oklahoma y de MIT Lincoln
  Laboratory ([Licencia](../referencia/licencia.md)): nunca en un registro público. El diseño original dice GHCR privado
  (`componentes.md`); el `registry.yml` de la infraestructura también sirve. La variable es `REGISTRY`.
- **La imagen base del ORPG**, `orpg-prod:b24`, en la máquina donde se construye el runner. No se toca su build.
- **Los repos hermanos** en la misma carpeta: `nexrad-l3-pipeline` en `main` con los commits `534d75f` y `ad8814c`
  (corrige [#11](https://github.com/vladimir1284/nexrad-l3-pipeline/issues/11)) o posteriores, y `lamula-webviewer`.
- **El visor, con el plano demo.** El PR #19 de `lamula-webviewer` ya está fusionado en `main` (`c7881ab`, 2026-11-09): la
  imagen `VIEWER_TAG` se construye desde `main`. Probado: esa imagen arranca y sirve los radares de `lamula_casos` con `casos_ro`.
- **Redes `traefik-public` y `postgres-public`** (las de la infraestructura existente) y Traefik con
  `certresolver` o con el certificado de origen de Cloudflare para los tres hostnames nuevos.
- **Un nodo para el worker**, con etiqueta: `docker node update --label-add jobs-worker=true <nodo>`.

!!! danger "Secretos: no en git"
    Los valores de `${...}` van en «Environment variables» de la pila en Portainer. Advertencia honesta: el código lee
    secretos **de variables de entorno**, no de ficheros, así que no se pueden usar Docker secrets sin cambiar código, y
    cualquiera con acceso al socket de Docker los ve en `docker service inspect`. Es el mismo nivel de exposición que
    tienen hoy las otras pilas.

    Aparte: `stacks/postgres.yml` de `ladetec_infrastructure` lleva contraseñas escritas en claro. No es de este
    proyecto, pero esta pila usa ese Postgres: conviene rotarlas y sacarlas de git.

## 3. Paso 1 — Construir y subir las imágenes

Tres imágenes. El orden no importa; la del runner exige la base del ORPG local.

```bash
# desde la raíz de lamula-jobs, con ../nexrad-l3-pipeline y ../lamula-webviewer en su sitio
REG=registro.ejemplo   # el privado
TAG=$(git rev-parse --short HEAD)

docker build -f jobs/Dockerfile --build-context pipeline=../nexrad-l3-pipeline \
  -t $REG/jobs-api:$TAG jobs

docker build -f job-runner/Dockerfile --build-context pipeline=../nexrad-l3-pipeline \
  -t $REG/job-runner:$TAG .

# desde una copia limpia: con `docker build .` en un clon con node_modules, pnpm aborta
# (ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY) porque `COPY . .` mete el node_modules local
( cd ../lamula-webviewer && git switch main && git pull --ff-only \
  && git archive HEAD | docker build -t $REG/lamula-webviewer:$TAG - )

docker push $REG/jobs-api:$TAG && docker push $REG/job-runner:$TAG && docker push $REG/lamula-webviewer:$TAG
```

Notas:

- El `Dockerfile` del visor no declara `ARG GIT_SHA`, así que el identificador de build del visor sale como `dev`. Es
  cosmético; arreglarlo es un cambio en `lamula-webviewer`, que esta guía no toca.
- **Arquitectura.** Las tres imágenes de arriba salen `linux/amd64`. El runner **no puede ser ARM**: la base del ORPG es solo
  `amd64` (binarios `lnux_x86`), así que `jobs-worker` va en un nodo `amd64`. `jobs-api` y el visor sí podrían ser ARM si algún nodo
  del Swarm lo es; desde la máquina x86_64 de desarrollo no se logró construirlas para ARM (ver [Pendientes](../alcance/pendientes.md)).
- Las migraciones del pipeline entran **dentro** de `jobs-api` (`/opt/pipeline/db/pg_migrations`). Si el pipeline añade
  una migración nueva, hay que reconstruir `jobs-api` y `job-runner`: la imagen lleva la copia de cuando se construyó.
- `docker build` del runner tarda lo que tarde instalar `python3.11` y `uv sync`; la base ya está construida.

**Comprobación.** Las tres imágenes están en el registro, y el runner no está en ninguno público:
`docker manifest inspect $REG/job-runner:$TAG`.

## 4. Paso 2 — Bases de datos

Las dos bases van en el Postgres compartido de la infraestructura (`pgvector/pgvector:pg16`). Las migraciones del
pipeline **no piden ninguna extensión** (se comprobó), así que no hace falta nada de `CREATE EXTENSION`.

### 4.1 `lamula_demo` (jobs con token)

Como superusuario, una sola vez:

```sql
CREATE DATABASE lamula_demo;
```

Desde cualquier sitio con acceso a esa base, una sola vez (el DSN es de **administración**, no se guarda en la pila):

```bash
docker run --rm --network postgres-public \
  -e JOBS_RW_SECRET=x -e JOBS_RO_SECRET=x -e JOBS_RESULT_SECRET=x \
  -e "JOBS_ADMIN_DSN=host=<pg> dbname=lamula_demo user=<superusuario> password=<...>" \
  $REG/jobs-api:$TAG jobs-admin migrate
```

Esto crea el schema `control`, las cuatro migraciones y los roles `jobs_api` y `jobs_runner` **sin login a propósito**.
La contraseña la pone el despliegue:

```sql
ALTER ROLE jobs_api    LOGIN PASSWORD '<JOBS_API_DB_PASSWORD>';
ALTER ROLE jobs_runner LOGIN PASSWORD '<JOBS_RUNNER_DB_PASSWORD>';
```

`jobs_api` es dueño de los schemas de job y puede crear y borrar roles (`CREATEROLE`); se comprobó que el barrido
(`jobs-admin sweep`, `health`, `orphans`) funciona con ese rol, sin superusuario. Cada job crea un schema `job_<id>` y dos
roles con `CONNECTION LIMIT 8`: ver el riesgo de `max_connections` en el apartado 11.

### 4.2 `lamula_casos` (casos preparados, D19)

Base distinta, dueño distinto. El contrato del pipeline va **tal cual, todas las migraciones**:

```sql
CREATE ROLE casos_rw LOGIN PASSWORD '<CASOS_RW_DB_PASSWORD>';
CREATE DATABASE lamula_casos OWNER casos_rw;
```

```bash
# las tres, en orden, como casos_rw, ANTES de procesar ningún caso
for f in 0001_init 0002_mosaic 0003_radar_height_feet_to_m; do
  psql "host=<pg> dbname=lamula_casos user=casos_rw" -v ON_ERROR_STOP=1 -f ../nexrad-l3-pipeline/db/pg_migrations/$f.sql
done
```

!!! danger "La migración 0003 y el orden"
    `0003` hace `UPDATE radars SET height_m = height_m * 0.3048`: convierte pies a metros. En una base **vacía** no
    hace nada y el pipeline nuevo escribe metros directamente. Si se aplica **después** de procesar casos con el pipeline
    nuevo, los divide otra vez. Orden correcto: migraciones primero, casos después, con una imagen del runner que
    lleve el arreglo (`534d75f` o posterior). En el ensayo local la base se creó con solo 0001 y 0002 y quedaron radares en
    pies y otro en metros; se corrigió a mano.

El visor de casos lee con un rol aparte, de solo lectura:

```sql
\c lamula_casos
CREATE ROLE casos_ro LOGIN PASSWORD '<CASOS_RO_DB_PASSWORD>';
GRANT CONNECT ON DATABASE lamula_casos TO casos_ro;
GRANT USAGE ON SCHEMA public TO casos_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO casos_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE casos_rw IN SCHEMA public GRANT SELECT ON TABLES TO casos_ro;
```

**Comprobación.** Con `casos_ro`, `SELECT count(*) FROM rasters` responde y `UPDATE radars SET height_m = 0` falla con
`permission denied`. (Probado así en local.)

## 5. Paso 3 — Buckets en R2

| Bucket | Contenido | Acceso público |
|---|---|---|
| `lamula-demo-raster` | COG de los jobs | **Lectura pública** por un hostname propio |
| `lamula-demo-staging` | volúmenes subidos por el cliente | **Privado** |
| `lamula-casos-raster` | COG de los casos | **Lectura pública** por un hostname propio |

Nombres por defecto de la pila; se cambian con `R2_BUCKET_DEMO`, `R2_BUCKET_STAGING` y `R2_BUCKET_CASOS`.

- **Los COG se leen desde el navegador**, así que los dos buckets de rasters necesitan acceso público de lectura y un
  hostname propio (`R2_PUBLIC_HOST_DEMO`, `R2_PUBLIC_HOST_CASOS`). Con la política cerrada el visor muestra «No se pudo cargar el
  COG»: es el fallo que dio el ensayo local con el bucket de jobs sin política.
- **Revisa CORS** del bucket para el origen de cada visor. Local no hay CORS que probar (moto), y el visor de producción
  ya lo resuelve para su bucket: copia esa regla.
- **Un token de API de R2** con lectura y escritura sobre los tres buckets. Lo usan el worker (publica y descarga) y el
  barrido (borra). Mejor dos tokens: el del barrido no necesita crear objetos.
- `R2_ENDPOINT` es `https://<id-de-cuenta>.r2.cloudflarestorage.com`.
- Un job borra sus objetos al caducar a los 7 días. Los casos no caducan y el barrido nunca toca `lamula_casos`
  ni su bucket (D19).

## 6. Paso 4 — DNS, Turnstile y correo

**Cloudflare DNS** (proxied, hacia el Swarm): `jobs.ladetec.com`, `demo.ladetec.com`, `casos.ladetec.com` y los dos
hostnames de los buckets. Comprueba que el certificado de origen que usa Traefik cubre los tres primeros (si es de
`*.ladetec.com`, sí).

**Turnstile** (Cloudflare → Turnstile → Add widget): dominio `demo.ladetec.com`. Da dos claves:

- *Site key* (pública) → `TURNSTILE_SITE_KEY`, la lee el visor.
- *Secret key* → `TURNSTILE_SECRET`, la lee `jobs-api`. Sin ella el formulario responde 503: cerrado por defecto.

Para ensayar sin riesgo existen claves de prueba de Cloudflare: el secreto `1x0000000000000000000000000000000AA` acepta
cualquier token. **No es para producción.**

**Brevo** (SMTP): crea una clave SMTP y verifica el remitente.

- `SMTP_HOST=smtp-relay.brevo.com`, `SMTP_PORT=587` (por defecto en la pila; el código hace `STARTTLS` y `login`).
- `SMTP_USER` y `SMTP_PASSWORD`: los de la página «SMTP & API» de Brevo (el usuario no es el correo de la cuenta).
- `MAIL_FROM`: un remitente **verificado** en Brevo, idealmente de `ladetec.com` con SPF y DKIM, o el token puede ir a spam.
- `ADMIN_EMAIL`: tu correo. **Quien controla ese buzón controla las aprobaciones**: el enlace del correo aprueba sin más
  autenticación. Los enlaces son de un solo uso y caducan a los 7 días.

## 7. Paso 5 — Crear la pila en Portainer

1. **Stacks → Add stack → Repository.** Repositorio de `lamula-jobs`, rama `main`, *Compose path*:
   `deploy/lamula-jobs.stack.yml`. Activa la autenticación si el repo es privado.
2. **Environment variables.** Una por una (o «Load variables from .env file» pegando una copia local; no la guardes en git):

| Variable | Valor |
|---|---|
| `REGISTRY`, `JOBS_TAG`, `RUNNER_TAG`, `VIEWER_TAG` | registro y etiquetas del paso 1 |
| `PG_HOST`, `PG_PORT` | el Postgres compartido, con el nombre que resuelve en `postgres-public` |
| `JOBS_API_DB_PASSWORD`, `JOBS_RUNNER_DB_PASSWORD` | las del paso 2.1 |
| `CASOS_RW_DB_PASSWORD`, `CASOS_RO_DB_PASSWORD` | las del paso 2.2 |
| `JOBS_RW_SECRET`, `JOBS_RO_SECRET`, `JOBS_RESULT_SECRET` | aleatorios, ≥32 bytes, **distintos entre sí** |
| `JOBS_INTERNAL_KEY` | aleatorio ≥32 bytes: lo comparten `jobs-api` y el visor de jobs |
| `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `ADMIN_EMAIL` | apartado 6 |
| `TURNSTILE_SECRET`, `TURNSTILE_SITE_KEY` | apartado 6 |
| `JOBS_HOST`, `DEMO_HOST`, `CASOS_HOST` | `jobs.ladetec.com`, `demo.ladetec.com`, `casos.ladetec.com` |
| `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | apartado 5 |
| `R2_PUBLIC_HOST_DEMO`, `R2_PUBLIC_HOST_CASOS` | hostnames públicos de los buckets de rasters |

Opcionales con valor por defecto: `SMTP_HOST`, `SMTP_PORT`, `R2_BUCKET_DEMO`, `R2_BUCKET_STAGING`, `R2_BUCKET_CASOS`.

!!! danger "Las tres claves `JOBS_*_SECRET` no se pueden cambiar a la ligera"
    Las contraseñas de los roles de cada job y el token de resultado **se derivan** de ellas (`tenancy.password`,
    `ids.token_resultado`), no se guardan. Cambiarlas deja huérfanos los jobs vivos: los enlaces de resultado dejan de
    valer y el barrido no puede borrar sus roles. Guárdalas fuera de Portainer también. `RW` y `RO` son distintas a
    propósito: el runner conoce `RW` y no `RO`, que es lo que ve el visor.

3. **Deploy the stack.** La pila falla al interpolar, con el nombre de la variable, si falta alguna obligatoria
   (comprobado: `required variable ADMIN_EMAIL is missing a value`). Si Portainer enseña eso, es una variable sin rellenar.

4. **Actualizar.** Para una versión nueva: construir y subir (paso 1), cambiar la etiqueta en las variables y *Update the
   stack*. El worker usa `update_config: stop-first` y `stop_grace_period: 60s`: nunca hay dos ORPG a la vez y el contenedor
   tiene 60 s para parar. Un job en curso al redesplegar queda reclamado: el barrido lo devuelve a la cola a los 120 s sin
   latido (D16). **Mejor desplegar sin jobs en curso**: `jobs-admin health` y la lista de jobs lo dicen.

## 8. Paso 6 — Comprobar que arrancó

Contra el Swarm real, en este orden. Todo menos el último punto es lo mismo que se ensayó en local.

```bash
# 1. los servicios arriba (6/6 con replicas 1)
docker stack services <pila>

# 2. el worker tiene al ORPG y al supervisor bajo arrancar.sh
docker exec $(docker ps -qf name=jobs-worker) pgrep -af 'arrancar|supervisor|lamula_jobs.worker|rssd'

# 3. desde fuera: entra el formulario y NO entra el resto
curl -s -o /dev/null -w '%{http_code}\n' https://jobs.ladetec.com/v1/public/cases        # 200
curl -s -o /dev/null -w '%{http_code}\n' https://jobs.ladetec.com/v1/jobs                # 404 (sin router)
curl -s -o /dev/null -w '%{http_code}\n' https://jobs.ladetec.com/v1/results/lmr_x       # 404 (sin router)
curl -s -o /dev/null -w '%{http_code}\n' https://jobs.ladetec.com/healthz                # 404 (sin router)
```

!!! note "Qué esperar del filtro"
    Un 404 en `/v1/jobs` desde fuera es **Traefik** sin router, no la API (que respondería 401). Si responde 401, el
    filtro de rutas no está funcionando y `jobs-api` está expuesta entera: revisa las etiquetas del servicio. Esto no se
    ha probado, porque no hay Traefik en local.

## 9. Paso 7 — Procesar los cinco casos

Una vez, con el worker vivo y las migraciones de `lamula_casos` aplicadas. Se lanzan con la imagen de `jobs-api` (el comando
crea un job con un token del sistema del nivel `casos`). Se probó con el superusuario; con el rol `jobs_api` hace lo mismo que
hace la API al crear un job, así que debería bastar, pero no se ha ejecutado así:

```bash
docker run --rm --network postgres-public \
  -e JOBS_RW_SECRET=<los de la pila> -e JOBS_RO_SECRET=<…> -e JOBS_RESULT_SECRET=<…> \
  -e "JOBS_ADMIN_DSN=host=<pg> dbname=lamula_demo user=jobs_api password=<…>" \
  -e PIPELINE_MIGRATIONS=/opt/pipeline/db/pg_migrations \
  $REG/jobs-api:$TAG sh -c 'for c in irma harvey michael ian milton; do jobs-admin caso $c; done'
```

Cada caso tarda **de 90 a 100 minutos con el ORPG real** (medido en local: Michael 5408 s, Ian 5369 s, Milton 97 min,
Harvey 91 min). Hay un solo worker, así que se procesan en cola, uno tras otro: cuenta unas **8 horas** para los cinco.
Solo puede haber un job vivo por caso, y uno fallido libera el nombre para repetirlo.

Comprobar el avance:

```bash
curl -s https://jobs.ladetec.com/v1/public/cases     # los que ya están `ready`
```

Resultado esperado en `lamula_casos` (cifras del ensayo local; las del real pueden diferir ±1 por el catálogo):

| Caso | Radar | Sitio | Rasters |
|---|---|---|---|
| Irma | KAMX | AMX | 75 |
| Harvey | KHGX | HGX | 99 |
| Michael | KEVX | EVX | 102 |
| Milton + Ian | KTBW | TBW | 84 + 77 = 161 |

Milton e Ian **comparten radar y base**; por eso `radars.last_seen_at` de TBW tiene que ser `2024-10-10T00:29:19`,
la fecha mayor, venga el caso que venga el último (corregido en `e08eafa`, con test).

Cada caso, una vez `ready`, se abre en `https://<CASOS_HOST>/<sitio>/153/<AAAAMMDDTHHMMSS>`. El producto 153 es
reflectividad base de súper-resolución.

## 10. Paso 8 — Ensayo de aceptación

Es la puerta de F4: alguien ajeno al equipo hace esto sin ayuda. Primero hazlo tú desde un navegador limpio y un
correo que no sea el tuyo.

1. Abre `https://<DEMO_HOST>/demo`. Ves los casos ya procesados y el formulario de acceso.
2. Pide acceso. Llega un correo a `ADMIN_EMAIL` con un enlace `https://<JOBS_HOST>/v1/requests/lmq_…/review`.
3. Abre el enlace: **solo muestra** la solicitud (un `GET` no aprueba nada; lo hacen solos los antivirus). Elige el nivel
   y pulsa *Aprobar*.
4. El solicitante recibe un correo con el código `lma_…` y el enlace al demo. El código se muestra una sola vez; en la base
   solo queda su `sha256`.
5. El solicitante lo pega en el demo, elige un radar y un día, lanza un job pequeño (2 volúmenes bastan).
6. Abre el enlace `/j/lmr_…` del resultado y ve la reflectividad con la etiqueta «no oficial».

Comprobaciones negativas, que en local dieron lo esperado:

| Prueba | Esperado |
|---|---|
| Abrir el enlace de revisión después de aprobar, o aprobar dos veces | 410 |
| `POST /v1/jobs` sin token, o con un token falso | 401 |
| Un job de 13 volúmenes con un token de nivel `demo` (límite 12) | 429 |
| `GET /v1/results/<token>` sin la clave interna | 401 |

## 11. Operación diaria

| Qué | Cómo |
|---|---|
| Ver solicitudes pendientes | `jobs-admin requests` |
| Aprobar o rechazar a mano | `jobs-admin approve <id> --tier demo`, `jobs-admin reject <id> [--avisar]` |
| Emitir un token sin formulario | `jobs-admin issue --email x --tier demo --org Y --days 30` |
| Revocar | `jobs-admin revoke <token_id>` |
| Jobs atascados, schemas o roles huérfanos | `jobs-admin health` y `jobs-admin orphans` (salen con 1 si hay algo) |
| Caducar un job ya | `jobs-admin expire <job_id>` |
| Repetir un caso | `jobs-admin caso <nombre>` (solo si el anterior falló o se borró) |
| Alarma de cola | los logs de `jobs-health` dicen `ALARMA`; **el canal de aviso sigue sin elegir** |

Todo `jobs-admin` se ejecuta con la imagen `jobs-api` y `JOBS_ADMIN_DSN`; las órdenes de consulta (`requests`,
`orphans`, `health`) caben con el rol `jobs_api`.

## 12. Riesgos que quedan, ordenados

1. **Conexiones a Postgres.** Cada job crea dos roles con `CONNECTION LIMIT 8`, y `server/dal/pg.ts` del visor **no desaloja
   nunca** su caché de conexiones: con un rol por job se come el `max_connections` del Postgres compartido, que es el de
   producción. Está listado en [Pendientes](../alcance/pendientes.md) como cambio necesario en `lamula-webviewer`. Con
   `max_connections=100` son unos veinte tokens de resultado abiertos entre reinicios del visor. **Hasta arreglarlo, reinicia
   `viewer-jobs` de vez en cuando o acota el nivel `demo`.**
2. **El demo comparte nodo con producción (D7).** El runner usa hasta 125 % de CPU de pico y 790 MiB con un volumen (F0), y
   el retraso del `processor` en vivo durante un job **no se ha medido**. Los límites de la pila (2 CPU, 3 GiB) son un punto
   de partida, no un valor medido. Mide con un job real y el `processor` en el mismo nodo antes de abrir a terceros.
3. **Licencia.** El runner es una imagen con código no redistribuible. Las dos cartas de consulta siguen sin enviar
   (`correspondencia/`). **No abras el demo a terceros antes de tener respuesta**: es una puerta de F4 que no es técnica.
4. **Un solo worker.** Los casos tardan unas 8 horas en cola y un job de cliente espera detrás. Subir réplicas exige otro
   ORPG y otro nodo con CPU libre; no se ha probado con más de una.
5. **Un producto malo tumba el job entero.** `l3proc` sale con código ≠ 0 y el worker da el job por fallido. #11 era un caso
   de esto; puede haber otros. El log del runner (`/data/jobs/<id>/runner.log`) dice cuál.
6. **`GREATEST` sobre texto en `last_seen_at`.** Funciona porque las fechas son ISO-8601; depende de que nadie escriba otro
   formato en esa columna.

## 13. Qué se probó y qué no

| Cosa | Estado |
|---|---|
| Camino de acceso completo en local: solicitud, correo (modo consola), aprobación de un solo uso, token, catálogo real por internet, job de 2 volúmenes `ready` en 9,5 min, resultado en el visor | **Probado** (2026-11-09) |
| Turnstile: llamada real a `siteverify` con la clave de prueba de Cloudflare | **Probado** (token ficticio aceptado) |
| Cuotas (429), 401 sin token y con token falso, 410 al reusar el enlace, 401 sin clave interna | **Probado** |
| Imagen `jobs-api`: `healthz`, migraciones del pipeline dentro, `jobs-admin` | **Probado** |
| `jobs-sweep` y `jobs-health` con el rol `jobs_api` (sin superusuario), sobre una base sin nada que barrer | **Probado** parcialmente: nunca vio un job caducado de verdad con ese rol |
| `arrancar.sh`: ORPG + supervisor + worker; job real `ready` en 10 min; `docker stop` en 26 s con código 0 | **Probado** (el ensayo destapó que faltaba `source ~/.bash_profile`; corregido) |
| Visor de casos con `casos_ro`, cuatro casos | **Probado** |
| Los cinco casos `ready` con el pipeline corregido | **Probado** en local; **no** en R2 ni en el Swarm |
| La pila: sintaxis, variables obligatorias y etiquetas | **Probado** con `docker compose config`; **no** desplegada |
| Traefik: filtro de rutas, límite de peticiones, certificados | **No probado** |
| Portainer leyendo la pila de git | **No probado** |
| Brevo (entrega real, SPF/DKIM, spam), Turnstile en navegador, formulario en móvil | **No probado** |
| R2: política pública, CORS, hostnames de buckets | **No probado** |
| Matar un caso a mitad de job y repetirlo | **No probado** (solo convergencia tras un fallo parcial de verificación) |
| `processor` live con un job en el mismo nodo | **No medido** |
| Ensayo de aceptación con alguien ajeno al equipo | **Pendiente**: es la puerta de F4 |
