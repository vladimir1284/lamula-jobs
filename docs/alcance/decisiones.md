# Decisiones de diseño

Congeladas salvo motivo nuevo. Cada una lleva la fecha en que se fijó y el porqué, para no
re-litigarlas.

## D1 — La entrada de un job es una lista de volúmenes Level II, no una fuente (2026-11-01)

El runner recibe claves en staging, no "un sitio y un día de AWS". La fuente vive en
`jobs-api`. Motivo: la segunda fuente (observaciones propias del cliente convertidas a Level
II) ya está comprometida, y con la fuente metida en el runner habría que reescribirlo.

## D2 — Sin subida de ficheros en la primera versión (2026-11-01)

Solo catálogo público de AWS. Motivo: elimina casi toda la superficie de validación y de
abuso, y cubre el caso que vende (un huracán del pasado). La subida llega con la herramienta
de conversión a Level II, no antes.

## D3 — Un solo runner persistente, sin socket de Docker (2026-11-01)

El runner es un servicio de larga vida que toma jobs de una cola y recicla el ORPG entre
trabajos con `mrpg -p startup`, que limpia todos los data stores. Motivo: la alternativa
—un orquestador que cree un contenedor por job— exige el socket de Docker, que es acceso root
al nodo. La concurrencia se obtiene con réplicas del runner, no con contenedores efímeros.

## D4 — Un schema de Postgres y un rol por job (2026-11-01)

Cada job tiene su `job_<ulid>` con el `0001_init.sql` del pipeline aplicado **tal cual**, y un
rol con `search_path` fijado a ese schema. Motivo: el viewer no cambia ni una consulta, el
contrato de datos no se toca, y borrar un job es `DROP SCHEMA ... CASCADE`. La alternativa
—una columna `dataset_id` en todas las tablas— es un cambio de contrato que tocaría pipeline,
viewer y Worker de ops.

## D5 — Bucket R2 y base de datos separados de producción (2026-11-01)

Los jobs escriben en `lamula-demo-raster` y en la base `lamula_demo`. Motivo: el sweep de
retención de 72 h del Worker `nexrad-l3-ops` borra por `created_at` y arrasaría con los jobs;
además un fallo del plano demo no debe poder tocar el demo live que ya está vendiendo.

## D6 — El demo es asíncrono (2026-11-01)

El cliente lanza el job y recibe un enlace. Reproducción a tiempo real (`play_a2 -T`, sin
`-x`), que es el único modo que la documentación de CODE respalda. Motivo: no hay razón para
arriesgar pérdida de radiales por acelerar algo que el cliente no está mirando.

Matiz que conviene explotar: como el watcher publica según llegan los productos, el enlace
funciona **mientras** el job corre y la línea de tiempo se va llenando.

## D7 — Mismo nodo del Swarm que producción (2026-11-01)

Sin nodo dedicado. Motivo: decisión del dueño del producto; no hay presupuesto para otro VPS
hoy. El riesgo (contención con el pipeline live) se acota con límites de CPU y memoria,
concurrencia 1 y la medición de F0. Ver [Límites y recursos](../operacion/limites-recursos.md).

## D8 — Sin cuentas: token de invitación con nivel de cómputo (2026-11-01)

El prospecto pide acceso por correo, nosotros emitimos el token a mano y el nivel del token
decide sus cuotas. Motivo: un demo que regala ~50 min de CPU por visitante no puede tener la
puerta abierta, y montar cuentas de verdad para una decena de prospectos es desproporcionado.

## D9 — Solo Level II formato V06 (2026-11-01)

El ORPG B24 espera Message 31. Los ficheros V03/V04/V05 no se ofrecen en el catálogo. Motivo:
compatibilidad; además el filtro es gratis, el sufijo está en la clave de S3.

**Matiz verificado el 2026-11-02** (no cambia la decisión, cambia cómo se implementa el
filtro): hasta 2015 el V06 se guarda envuelto en gzip, con la clave terminada en `_V06.gz`, y
en el archivo hay también **V07** (KEVX en 2013, cabecera `AR2V0007.706`), que D9 no nombraba.
El filtro va por lista blanca —`_V06` y `_V06.gz`— y nunca por lista negra. Además, el límite
inferior del catálogo seleccionable es por radar, entre 2012 y 2014. Medidas en
[Catálogo verificado](../referencia/catalogo-verificado.md).

## D10 — El listado del catálogo AWS vive en el servidor (2026-11-01)

`jobs-api` lista el bucket con boto3 anónimo, aunque el bucket tenga CORS y el navegador
pudiera hacerlo. Motivo: el job necesita fijar su lista de claves de forma autoritativa para
validarla y para poder reintentar; listar también en el cliente duplica la lógica y ata el
demo a que el bucket mantenga CORS.
