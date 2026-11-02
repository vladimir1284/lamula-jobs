# Aislamiento de datos

## Por job: un schema y un rol

```sql
CREATE SCHEMA job_<ulid>;
CREATE ROLE job_<ulid> LOGIN PASSWORD '<generada>';
ALTER ROLE job_<ulid> SET search_path = job_<ulid>;
GRANT USAGE ON SCHEMA job_<ulid> TO job_<ulid>;
```

Sobre ese schema se aplican las migraciones de `db/pg_migrations/` de `nexrad-l3-pipeline`
**sin modificarlas**, con el `search_path` apuntando al schema del job. El runner escribe con
ese rol; el viewer lee con un rol gemelo de solo lectura.

!!! note "Las migraciones, todas, no solo la primera"
    Revisado el 2026-11-02. El `0001_init.sql` no trae extensiones, ni tipos, ni nombres
    calificados con `public.`, así que se aplica a un schema cualquiera sin tocar una línea: la
    única cosa global que crea es la secuencia del `BIGSERIAL` de `rasters`, que vive dentro
    del schema y se va con el `DROP SCHEMA ... CASCADE`.

    Pero hay que aplicar también `0002_mosaic.sql`, aunque un job no haga mosaicos. El motivo
    está en el viewer: `pages/[site]/[product]/[[time]].vue:73` pide `/api/mosaic/domains` en
    **la propia vista de un radar**, para saber si ofrecer el enlace al mosaico, y esa ruta
    hace `SELECT ... FROM mosaic_domains`. Sin la tabla, esa petición falla en cada carga de
    página. Con las tablas vacías, devuelve una lista vacía y no se ofrece el enlace, que es
    justo lo que queremos.

Consecuencias, todas buenas:

- El viewer no cambia ni una consulta: ya lee `FROM radars`, sin calificar.
- El contrato de datos sigue siendo el del pipeline, y si el pipeline migra, los jobs nuevos
  heredan la migración sin trabajo.
- Borrar un job es `DROP SCHEMA ... CASCADE` más `DROP ROLE`.
- Dos jobs del mismo radar y la misma fecha no colisionan, pese al `UNIQUE (site_id,
  product_code, vol_time)` de `rasters`.

Lo que hay que vigilar: número de schemas y de roles a lo largo del tiempo (el cron de
expiración es parte del diseño, no un extra), y el número de conexiones.

!!! danger "El caché de conexiones del viewer no desaloja nada"
    Revisado el 2026-11-02: `server/dal/pg.ts` guarda las conexiones en un `Map` indexado por
    `host:puerto/base@usuario`, con `max: 5` por entrada, y **no borra ninguna entrada nunca**;
    tampoco hay `idle_timeout` ni `max_lifetime`. En producción eso está bien, porque hay un
    solo juego de credenciales. Con un rol por job, cada token que alguien abra deja hasta
    cinco conexiones vivas para el resto de la vida del proceso.

    El límite no es entonces "jobs simultáneos" sino **jobs distintos vistos desde que se
    arrancó el viewer**. Con un `max_connections` de 100 eso son unos veinte tokens, y después
    el viewer deja de poder abrir nada, incluido el job que está corriendo.

    Dos salidas, las dos pequeñas y aditivas en `pg.ts`: bajar `max` a 1 o 2 para el viewer
    demo —un prospecto mirando su propio job no necesita cinco— y desalojar por LRU llamando a
    `sql.end()` al sacar una entrada del `Map`. Conviene decidirlo en F3 y no al encontrarse
    el Postgres sin conexiones.

## Por job: prefijo en R2

Bucket `lamula-demo-raster`, claves `jobs/<ulid>/` por delante de la convención del pipeline.
El pipeline hoy no soporta prefijo configurable (`ingest/storage/keys.py` lo construye fijo),
así que hace falta un cambio pequeño y aditivo allí: `R2_KEY_PREFIX`, vacío por defecto.

Alternativa sin tocar el pipeline: un bucket por job. Descartada — las cuotas de R2 y el
trabajo de configurar CORS y hostname por bucket no lo justifican.

## Retención

| Qué | Cuándo | Quién |
|---|---|---|
| Schema y rol del job | Al expirar el job (según el nivel del token) | Cron de `jobs-api` |
| Objetos en R2 del job | Al expirar, y con regla de ciclo de vida por prefijo como red | Cron + R2 |
| Staging del job | Al terminar el job, con éxito o sin él | Runner |
| Logs del job | Más tiempo que el job: sirven para depurar un fallo ya reportado | Cron |

## Lo que nunca comparte con producción

- Base de datos distinta de la del pipeline.
- Bucket distinto del de producción.
- El Worker `nexrad-l3-ops` no ve nada de esto: su sweep de 72 h y su reconciliación siguen
  operando solo sobre los almacenes live.
