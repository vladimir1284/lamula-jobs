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

## D6 — El demo es asíncrono; reproducción con `play_a2 -m` (2026-11-01, revisada 2026-11-02)

El cliente lanza el job y recibe un enlace. Como el watcher publica según llegan los productos,
el enlace funciona **mientras** el job corre y la línea de tiempo se va llenando.

**Decisión original (2026-11-01):** `play_a2 -T`, el único modo que respalda la documentación de
CODE, para no arriesgar pérdida de radiales.

**Revisión del 2026-11-02, decidida por el dueño del producto:** se usa el modo más rápido
siempre que no afecte a los resultados. F0 lo midió (12 volúmenes de Irma, KAMX, enlace con
`LR` alto): los tres modos dan los mismos productos (106 huellas, tolerancia 0,1 %, 0
diferencias) y `-m` fue el más rápido, 4 662 s frente a 4 808 s (sin `-T`) y 4 903 s (`-T`).
Por tanto **el modo por defecto del runner es `play_a2 -m -d <dir>`**. Ver
[Velocidad de reproducción](../referencia/velocidad-reproduccion.md).

Límites que conviene no olvidar:

- La ganancia es de ~5 % con **una sola corrida por modo**: está dentro de lo que podría ser
  ruido. La decisión se sostiene por «no empeora nada y no cuesta nada», no por el tiempo.
- El motivo por el que no se aceleró más es que **el cuello de botella es el ORPG**, no el reloj
  de `play_a2` (~6,5 min por volumen de KAMX; perfilado el 2026-11-02: el ORPG espera, no calcula; ver [Perfil del ORPG](../referencia/perfil-orpg.md)). El demo sigue
  costando ~80 min de nodo por 12 volúmenes, así que **sigue siendo asíncrono** y las cuotas de
  D8 se calculan con ese coste.
- Si una repetición futura mostrara productos distintos entre modos, `-T` vuelve a ser el
  modo por defecto sin discutirlo.

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
corrida `-m`. Lo primero evita el fallo —**confirmado el 2026-11-02**: con `LR=1536000` la pasada `-T` de 12
volúmenes salió con 0 truncados y 106 de 106 productos decodificados, frente a 8 de 12 N0B
truncados con `LR=100000`—; lo segundo lo detecta si
reaparece por cualquier otra causa. Una sola de las dos deja un fallo silencioso o un job que
falla sin remedio. Sin ninguna, un COG con un hueco sin explicación.


## D12 — La puerta de F1 se cierra con COGs en disco; R2 pasa a F2 (2026-11-03)

F1 termina cuando doce volúmenes de un huracán salen como COGs en disco, con el `vol_time` y la
georreferenciación correctos, decodificados por `l3proc` sobre una copia de la salida del ORPG
y sin publicar. La publicación en R2 (y en la base que use el pipeline) se hace en F2.

Motivo: decisión del dueño. No hay credenciales de R2 para probar y la publicación no cambia lo
que F1 tiene que demostrar, que es la cadena ORPG → producto → COG.

## D13 — Dos roles de servicio y contraseñas de job derivadas, no guardadas (2026-11-04)

`jobs-api` y el runner no se conectan como el mismo rol. **`jobs_api`** es dueño de los schemas de
job, crea y borra schemas y roles, y lo ve todo en `control`. **`jobs_runner`** solo puede leer
`jobs` y `job_inputs` y actualizar siete columnas de progreso (`state`, `claimed_*`, `heartbeat_at`,
`attempts`, `error`, `started_at`, `finished_at`): no ve los tokens de acceso, no puede cambiar la
cuota ni la caducidad de nadie y no puede crear schemas ni roles
(`tests/test_cola.py::test_runner_no_puede_tocar_cuotas_ni_tokens_ni_crear_schemas`).

Las contraseñas de los dos roles de cada job (`job_<id>` escribe, `job_<id>_ro` lee) se **derivan**
con HMAC-SHA256 de una clave del servicio y el id del job. No hay columna de contraseñas que
filtrar, y quien conoce la clave puede volver a calcularlas. Son dos claves distintas: el runner
conoce la de escritura y **no** la de lectura (lo que el viewer usa), y el token de resultado se
deriva de una tercera.

Motivo: un runner comprometido es lo más expuesto del plano demo (ejecuta software con licencia
ajena sobre ficheros de terceros). Con esto no llega ni a los tokens ni a otros jobs.

Las tablas de cada schema pertenecen a `jobs_api`, no al rol del job: un job no puede alterar la
forma de su schema (`ALTER TABLE` y `CREATE TABLE` dan `InsufficientPrivilege` en las pruebas).

## D14 — Dos jobs vivos no pueden cubrir el mismo radar en las mismas horas (2026-11-04)

Mientras el pipeline no admita `R2_KEY_PREFIX`, el alta de un job se rechaza (HTTP 409) si otro job
vivo (`creating`, `queued`, `claimed`, `ingesting`, `ready`) del mismo radar tiene una ventana
`[vol_from, vol_to]` que se solapa con la suya.

Motivo: el pipeline escribe cada COG en `{site}/{producto}/{aaaa}/{mm}/{dd}/{site}_{producto}_{ts}.tif`,
sin nada del job. Dos jobs del mismo radar y la misma hora escribirían **el mismo objeto**, y el
borrado de uno (que se hace por las claves de su propio schema) se llevaría el del otro. Medido: no
se pisan en la base —cada job tiene su schema— pero sí en el bucket. Rechazar el alta es peor para
el usuario que arreglarlo, y es mejor que corromper en silencio.

**Se retira** cuando el pipeline acepte `R2_KEY_PREFIX` (cambio pequeño y aditivo, ya propuesto en
[Aislamiento de datos](../arquitectura/aislamiento-datos.md)) o si el dueño decide un bucket por
job. El efecto práctico hasta entonces: **dos prospectos no pueden mirar a la vez el mismo huracán
en el mismo radar con jobs propios**; F4 (casos preparados, jobs compartidos) lo resuelve de otra manera.

## D15 — Un alta pasa por `creating` antes de ser visible para los runners (2026-11-04)

La fila del job se inserta en `creating`; solo cuando el schema y los roles existen, pasa a `queued`.
Un alta que muere entre las dos cosas queda en `creating` y el barrido la marca `failed` pasados 10
minutos. Motivo: sin ese estado, un runner podía reclamar el job milisegundos antes de que existiera
su schema. Las cuotas cuentan `creating` como activo.

## D16 — Un runner sin latido durante 120 s se da por muerto (2026-11-05)

El barrido devuelve a la cola, o marca `failed`, al job reclamado cuyo último latido tiene más de
**120 s** (antes 600). `jobs-admin health` avisa a los **60 s**, para llegar antes que el barrido.

Motivo, medido: con un job real de 12 volúmenes (84 min, ORPG a pleno) el mayor hueco entre
latidos fue **13,2 s** y no hubo ninguno de más de 30 s
([Resultados de F2](../referencia/f2-resultados.md#margen-del-timeout-de-runner-muerto-2026-11-05)).
120 s deja nueve veces ese margen y recorta lo que tarda en liberarse un job de un worker muerto: el
ORPG huérfano sigue reproduciendo hasta que alguien reclama el job, y con 600 s eran hasta ~10 min de
nodo pagado de la cuota del cliente.

**Se revisa si** el pipeline live pasa a compartir nodo con el runner: la medida es de un job solo, y
con contención el hueco puede crecer. Es una constante (`sweep.TIMEOUT_MUERTO_S`), no un contrato.

`jobs-admin expire <job>` (misma fecha) caduca a mano un job `ready` o `failed` y borra ya su schema,
roles y objetos. Sin él, un job `ready` bloquea su radar y sus horas (D14) hasta que caduca, meses
después, y no había otra forma de liberarlo. En cola o en marcha no actúa: se cancela primero.

## D17 — El runner publica por lotes mientras el ORPG reproduce (2026-11-05)

`runner orpg` suelta a `prod/` cada producto que ya está entero (`entero()`) y quieto (mismo tamaño y mtime
en dos sondeos de 5 s); el worker, cada 15 s, copia lo nuevo a un directorio de lote y lanza
`l3proc watch --once` sobre él. Tras cada lote verifica coordenadas y fija `last_seen_at`, así un
`change_radar` que no surtió efecto falla con el primer lote y no con el último. Un lote con fallidos hace
fallar el job; un truncado de verdad nunca sale de `tmp` y lo encuentra `revisar()` al final (D11).

Motivo: la puerta de F3 es que un enlace abierto *mientras* el job corre muestre los productos
apareciendo. Medido ([Resultados de F2](../referencia/f2-resultados.md#publicacion-durante-el-job-2026-11-05)).
Lo que no cambia: el schema, el contrato del pipeline y `l3proc` (sin tocar el repo ajeno).
