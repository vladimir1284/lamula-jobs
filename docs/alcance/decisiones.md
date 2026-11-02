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

Cada job tiene su `job_<ulid>` con las migraciones del pipeline aplicadas **tal cual**, y un
rol con `search_path` fijado a ese schema. (Todas las migraciones, no solo la primera: el
viewer consulta las tablas del mosaico desde la vista de un radar. Ver
[Aislamiento de datos](../arquitectura/aislamiento-datos.md).) Motivo: el viewer no cambia ni una consulta, el
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

**Evidencia nueva del 2026-11-02, que no revierte la decisión pero la pone sobre la mesa.**
Leído el fuente de `play_a2`: nada en el reproductor descarta radiales por ir rápido, `-T` no
significa "a tiempo real" sino "simula también el hueco entre volúmenes", y existe `-m`, que
reproduce a la máxima velocidad con control de flujo del propio RPG. Con los números de las
ventanas propuestas, `-T` cuesta unos 85 minutos de nodo por job, mientras que saltarse los
huecos costaría del orden de 60 y `-m` posiblemente mucho menos.

No se cambia nada hasta que F0 mida las tres y `f0/equivalencia.py` diga si los productos son
los mismos. Si lo son, el motivo de D6 —"no arriesgar pérdida de radiales por acelerar algo que
el cliente no mira"— deja de aplicar tal cual está escrito, y el demo pasa de tardar una hora y
media a tardar minutos. Eso cambia también las cuotas y hasta si el demo tiene que ser
asíncrono.

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

## D11 — Un job no se da por bueno sin comprobar la integridad de sus productos (2026-11-02)

Dos cosas, las dos en F1. **La imagen del runner hornea `LR` alto en `comms_link.conf`**
(1536000, no el 100000 del primer runbook), y **`f0/integridad.py` es una puerta de cada job**:
la longitud declarada en la cabecera de cada producto tiene que coincidir con el tamaño en disco,
y un producto de más de 1 KB que no cuadre falla el job. Los `GSM…` y `P173_…` se filtran antes
de entregar al pipeline.

Motivo: en la primera ejecución real, `nbtcp` guardó N0B truncados sin ningún error (cierra los
sockets a los 30 s de empezar cada producto, `nbtcp_process_rpg_msgs.c:90`), 4 de 7 en la
corrida `-m`. Lo primero evita el fallo —**hipótesis aún sin confirmar**; si la pasada `-T`
sale con truncados, la causa es otra y esta decisión se reescribe—; lo segundo lo detecta si
reaparece por cualquier otra causa. Una sola de las dos deja un fallo silencioso o un job que
falla sin remedio. Sin ninguna, un COG con un hueco sin explicación.

