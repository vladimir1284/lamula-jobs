# Aislamiento de datos

## Por job: un schema y un rol

```sql
CREATE SCHEMA job_<ulid>;
CREATE ROLE job_<ulid> LOGIN PASSWORD '<generada>';
ALTER ROLE job_<ulid> SET search_path = job_<ulid>;
GRANT USAGE ON SCHEMA job_<ulid> TO job_<ulid>;
```

Sobre ese schema se aplica el `db/pg_migrations/0001_init.sql` de `nexrad-l3-pipeline` **sin
modificarlo**, con el `search_path` apuntando al schema del job. El runner escribe con ese rol;
el viewer lee con un rol gemelo de solo lectura.

Consecuencias, todas buenas:

- El viewer no cambia ni una consulta: ya lee `FROM radars`, sin calificar.
- El contrato de datos sigue siendo el del pipeline, y si el pipeline migra, los jobs nuevos
  heredan la migración sin trabajo.
- Borrar un job es `DROP SCHEMA ... CASCADE` más `DROP ROLE`.
- Dos jobs del mismo radar y la misma fecha no colisionan, pese al `UNIQUE (site_id,
  product_code, vol_time)` de `rasters`.

Lo que hay que vigilar: número de schemas y de roles a lo largo del tiempo (el cron de
expiración es parte del diseño, no un extra), y el número de conexiones, ya que cada rol abre
su propio pool. Con `max: 5` por conexión en el viewer, el tope de jobs vivos simultáneos tiene
que caber en `max_connections` del Postgres compartido.

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
