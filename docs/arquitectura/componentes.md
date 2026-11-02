# Componentes

Tres servicios nuevos en el Swarm, más dos almacenes nuevos. Nada de lo existente cambia de
comportamiento.

## `jobs-api` (FastAPI)

Única cara pública. Responsabilidades:

- Valida el token de acceso y aplica sus cuotas ([Acceso y cuotas](../operacion/acceso-y-cuotas.md)).
- Lista el catálogo de fuentes con boto3 anónimo (D10) y resuelve una selección del cliente a
  una **lista ordenada de claves**.
- Crea el job: fila en la cola, schema y rol del job, token de resultado.
- Sirve el estado del job al cliente (polling) y el enlace al viewer demo.
- Cron de expiración: borra schemas, roles y objetos de jobs vencidos.

No procesa nada. No habla con el ORPG.

## `job-runner` (imagen propia, privada)

Imagen construida **sobre** `ghcr.io/vladimir1284/orpg:b24` con el pipeline instalado encima
(`uv` + `l3proc`). Privada en GHCR porque contiene binarios del ORPG.

Servicio de larga vida. Bucle: toma un job con `SELECT ... FOR UPDATE SKIP LOCKED`, lo ejecuta
entero ([Ciclo del runner](ciclo-runner.md)), vuelve a esperar. Concurrencia = número de
réplicas; arranca en 1.

Dentro del contenedor conviven, por job:

| Proceso | Papel |
|---|---|
| `mrpg` + 107 tareas del ORPG | Genera los productos |
| `play_a2` | Inyecta los volúmenes Level II |
| `nbtcp` | Usuario Class 1 simulado; escribe los productos a disco |
| `l3proc watch` | Decodifica, hace el COG y publica a R2 + Postgres |

## `viewer-demo` (lamula-webviewer, segunda instancia)

Misma imagen que el viewer de producción, otra configuración:

- `NUXT_PUBLIC_R2_BASE_URL` → hostname del bucket demo.
- Credenciales de Postgres **por petición**, derivadas del token del job en la ruta
  `/j/<token>`. `server/dal/pg.ts` ya cachea conexiones por credenciales, así que esto encaja
  sin rediseñar el DAL.
- Capas de viento y rayos ocultas cuando el job es histórico: no hay GFS ni GLM para 2017.

Cambios necesarios en el repo del viewer, todos aditivos:

1. Resolver credenciales a partir del token del job (middleware de servidor).
2. Inicializar la línea de tiempo en la ventana del job en vez de "lo más reciente".
3. Pantalla de estado mientras el job no está listo.

## Almacenes

| Almacén | Qué es | Por qué separado |
|---|---|---|
| `lamula-demo-raster` (R2) | COGs de los jobs, con hostname propio y CORS | El sweep de 72 h de producción no lo ve (D5) |
| Base `lamula_demo` (mismo Postgres) | Un schema por job | Aislamiento barato y borrado atómico (D4) |
| Prefijo de staging en R2 | Volúmenes Level II descargados para un job | Permite reintentar sin volver a bajar de AWS |

## Qué no se toca

- El Worker `nexrad-l3-ops` no monitoriza jobs. Su trabajo es alertar sobre el feed live.
- El schema del pipeline no cambia. Ni una columna.
- El `processor` de producción no comparte directorio ni base con el runner.
