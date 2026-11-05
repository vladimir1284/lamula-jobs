# Pendientes

Huecos abiertos, ordenados por lo que bloquean.

## Bloqueantes de F0

- **Encabezado WMO en la salida de `nbtcp`.** Resuelto en el fuente el 2026-11-02: `nbtcp`
  escribe el producto pelado **salvo que se le pase `-A`**, y sin encabezado `l3proc process`
  muere con `AttributeError` en `siteID` antes de publicar nada. Queda una decisión de
  producto, no técnica: `-A` pone el enrutado de la oficina real del NWS. Ver
  [Contrato con el pipeline](../referencia/contrato-pipeline.md).
- **Automatizar `nbtcp`.** Casi resuelto en el fuente: con `-A` desaparece la pregunta de la
  convención de nombres, con `-b` el programa se va a segundo plano y deja de leer el terminal,
  y la única entrada que queda —el nombre de la RPS list— se lee con `scanf`, así que un
  `echo` por delante basta. **Falta ejecutarlo**: que compile así no garantiza que se comporte
  así. El plan B (leer el product LB) sigue en pie, pero ha bajado mucho de probabilidad.
- **Aislamiento entre jobs.** Comprobar que `mrpg -p startup` no deja rastro del job anterior.
  Un producto filtrado es un fallo silencioso.
- **Decodificación de la salida de `nbtcp`.** Corregido el 2026-11-02 un error de esta
  página: los ficheros del bucket de Unidata **sí** traen cabecera WMO, 30 bytes de texto
  (`SDUS52 KMFL 010000\r\r\nN0BAMX\r\r\n`). Lo demás del producto decodifica igual con y
  sin ella; lo único que se pierde es `siteID`, que es justamente lo que el pipeline necesita
  (punto de arriba).
- **Velocidad segura de reproducción.** Replanteado el 2026-11-02 con el fuente delante
  ([Hechos verificados del ORPG](../referencia/orpg-hechos.md)): `play_a2` no descarta nada por
  ir rápido —`-x` solo escala la cuenta de la espera—, `-T` no es "tiempo real" sino "simula
  también el hueco entre volúmenes", y existe `-m`, que va a la máxima velocidad **con control
  de flujo del propio RPG**.

  Lo que F0 tiene que medir es, por tanto, otra cosa: los mismos doce volúmenes por los tres
  caminos (`-T`, sin `-T`, `-m`), comparando duración y, con `f0/equivalencia.py`, que los
  productos salgan iguales. Si salen iguales, la diferencia es puro tiempo de nodo. Ver el
  matiz añadido a D6 en [Decisiones](decisiones.md).

## Bloqueantes de la apertura a terceros

La pregunta de licencia está **resuelta y es mala noticia**: ver
[Licencia del CODE](../referencia/licencia.md). El paquete no trae licencia, pero sí código de
la Universidad de Oklahoma con cláusula no comercial y con "not to be provided or used in any
format", y código de MIT Lincoln Laboratory reproducible solo "by or for the U.S. Government".
Los tres se compilan hoy.

!!! warning "En consulta — no tocar ningún build"
    El 2026-11-02 el dueño del producto se llevó este asunto a consultar con los dueños del
    código. **Hasta que vuelva con una respuesta, no se modifica el build de `radar-orpg-dev`
    ni el de este repo.** Lo de abajo es el menú de opciones que hay sobre la mesa, no una
    lista de tareas asignadas.

Opciones identificadas, para cuando haya respuesta:

- **Excluir del build** `src/cpc004/tsk015`, `tsk017`, `tsk019` y `src/cpc023/tsk006`,
  comprobando que el enlazado del resto aguanta. Tocaría `radar-orpg-dev`, no este repo.
- **Averiguar si `src/cpc101/tsk001` es prescindible.** Es ingesta de rejillas de modelo; habría
  que confirmar que DAA, DU3 y DTA no dependen de él antes de plantearse cortarlo.
- **Acotar si la imagen sale alguna vez de nuestra infraestructura.** Si el prospecto nunca hace
  `pull` y solo ve productos renderizados en nuestra web, el problema de distribución
  desaparece y queda solo el de uso.
- **Pedir la postura por escrito**, por dos vías en paralelo —la NWS no puede responder por la
  Universidad de Oklahoma, y esperar una respuesta para escribir la otra cuesta semanas—. Los
  dos borradores están escritos y esperan revisión en `correspondencia/`:
  `2026-11-02-istok-licencia.md` (NWS) y `2026-11-02-ou-licencia.md` (OU).
- **Etiquetado de salida**: los productos del demo no pueden presentarse como oficiales del
  NWS, ni usar su nombre o identificadores. Esto toca la interfaz del viewer demo y es trabajo
  de F3 pase lo que pase con lo demás.

Nada de esto bloquea F0 ni F1, que corren en nuestra máquina y para nuestro desarrollo. Bloquea
F4, que es cuando entra el primer tercero.

## Decisiones que faltan

- Dominio del viewer demo y del hostname del bucket.
- Texto y campos exactos del formulario de solicitud de acceso. Hay un borrador completo en
  [Acceso y cuotas](../operacion/acceso-y-cuotas.md), pendiente de aprobar o cambiar.
- Si el enlace de resultado caduca a la vez que el job o sobrevive un tiempo en solo lectura.

### Umbral de huecos — con datos, falta decidir

Medido el 2026-11-02 (ver [Catálogo verificado](../referencia/catalogo-verificado.md)): la
ventana de Irma en KAMX tiene un hueco de **10 minutos exactos** y cuatro volúmenes parciales
seguidos de huecos de 47 a 109 s. Con `play_a2 -T`, un hueco de diez minutos son diez minutos
de nodo parado, pagados de la cuota del cliente.

Propuesta, para aprobar o tumbar: **cortar el job en el primer hueco mayor de dos veces la
cadencia mediana de la ventana**, avisando antes de confirmar. Es automático, no necesita saber
el VCP y se explica en una frase al cliente.

### Cambio de VCP a mitad de ventana — con datos, falta decidir

No es hipotético: **Harvey, uno de los cinco casos preparados, cambia de VCP 121 a VCP 212** a
las 01:50:52 UTC, hora y media después del comienzo de la ventana. Medido, no supuesto.

Lo que hay que averiguar en F0 es si el ORPG lo absorbe solo —es exactamente lo que le pasa a
un RPG operativo cuando el operador cambia de patrón— o si hay que cortar. La hipótesis de
trabajo es que lo absorbe; si es así, no hace falta ni avisar.

### Tope de bytes por job, además del tope de volúmenes

Un volumen de huracán ocupa de 12 a 25 MB; uno de día tranquilo, 5,9 MB. Las cuotas de
[Acceso y cuotas](../operacion/acceso-y-cuotas.md) están expresadas solo en número de
volúmenes, así que el mismo nivel `demo` mueve entre 70 MB y 300 MB de staging. Propuesta:
añadir `max_bytes` a la tabla `tiers` y validarlo al crear el job, que es cuando `jobs-api` ya
conoce el tamaño de cada clave.

## Cambios necesarios en repos ajenos

| Repo | Cambio | Tamaño |
|---|---|---|
| `nexrad-l3-pipeline` | `R2_KEY_PREFIX` opcional en `ingest/storage/keys.py` | pequeño, aditivo |
| `nexrad-l3-pipeline` | **`height` del producto está en pies y se guarda como metros** (`decoder/level3.py`, `radars.height_m`, y de ahí al peso del mosaico). Error de 178 m en un radar costero y de 4,1 km en ABX. Ver [Contrato con el pipeline](../referencia/contrato-pipeline.md) | pequeño, **con migración de datos** |
| `nexrad-l3-pipeline` | `site_id` explícito cuando el producto no trae encabezado WMO — `decoder/level3.py:166`, `phenomena/parse.py:236`, `phenomena/vwp.py:68`. Ver [Contrato con el pipeline](../referencia/contrato-pipeline.md) | pequeño, aditivo |
| `lamula-webviewer` | Credenciales por token de job (`server/dal/index.ts`; `pg.ts` ya cachea por credenciales), línea de tiempo en la ventana del job, pantalla de estado, ocultar viento y rayos en jobs históricos | mediano, aditivo |
| `lamula-webviewer` | Desalojo del caché de conexiones de `server/dal/pg.ts` y `max` más bajo: hoy no desaloja nunca, y con un rol por job se come el `max_connections` del Postgres compartido. Ver [Aislamiento de datos](../arquitectura/aislamiento-datos.md) | pequeño, aditivo |
| `lamula-jobs` (no ajeno, pero va aquí por parejo) | `UPDATE radars SET last_seen_at` al cerrar el job, o el selector de días del viewer sale vacío en jobs históricos | una línea |
| `lamula-process` | Ninguno. De ahí solo se porta conocimiento y datos. | — |

## Deuda consciente

- Un job es de un solo radar: sin mosaico.
- Sin viento ni rayos históricos.
- Sin productos 59, 61 y 62 pese a que el ORPG los genera.


## Abiertos tras F2 (2026-11-05)

- **`R2_KEY_PREFIX` en el pipeline.** Sin él rige D14 (no hay dos jobs vivos del mismo radar y horas).
  Es un cambio pequeño y aditivo en `nexrad-l3-pipeline` (`ingest/storage/keys.py`); **no se ha tocado ese
  repo**. Decide el dueño: pedir el cambio, o un bucket por job.
- **Publicación durante el job.** Condición de la puerta de F3: el runner tiene que entregar productos al
  pipeline por lotes mientras `play_a2` reproduce, no al final. Ver
  [Resultados de F2](../referencia/f2-resultados.md#lo-que-f2-no-hace-todavia).
- **Cómo se supervisa el worker dentro de la imagen** (el `ENTRYPOINT` heredado ignora el comando).
- **Quién programa el barrido** (`jobs-admin sweep`) y con qué frecuencia; y el timeout de runner muerto
  (hoy 600 s, sin medir con un job real largo).
- **Credenciales y bucket reales** (R2 demo, base `lamula_demo`): del dueño.
- **Número de conexiones por job**: el límite del rol de job es 8 (`CONNECTION LIMIT`); con el viewer de
  F3 hay que medirlo junto con la nota de `server/dal/pg.ts`.
