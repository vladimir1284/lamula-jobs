# Fases

Cada fase tiene una puerta: algo comprobable que decide si se sigue. La F0 puede matar el
proyecto en una tarde, que es exactamente para lo que está.

## F0 — Espiga manual (bloqueante)

Un contenedor a mano, sin servicios, sin cola, sin API. Un volumen real descargado de
`unidata-nexrad-level2`.

1. `change_radar` al sitio del volumen, `mrpg -p -v startup`.
2. `nbtcp -A -b` con una RPS list recortada a los diez productos del pipeline, y el nombre de
   esa lista por stdin. El porqué de cada opción, leído del fuente, en
   [Hechos verificados del ORPG](../referencia/orpg-hechos.md).
3. `play_a2 -d directorio` (no `-p`: no lee el formato del bucket) con uno o dos volúmenes, y después la comparación de los tres modos
   de velocidad (`-T`, sin `-T`, `-m`): duración de cada uno y, con `f0/equivalencia.py`, si
   los productos salen iguales. Resultado: iguales, y D6 quedó en `-m` (2026-11-02).
4. Decodificar los productos resultantes con `l3proc process`.

**Puertas:**

- `nbtcp -A -b` se automatiza sin terminal interactiva. El fuente dice que sí; falta verlo.
  Si no, se evalúa el plan B (leer el product LB) antes de seguir.
- Los productos que escribe traen el encabezado WMO de 30 bytes y `l3proc process` los digiere
  sin cambios. Sin `-A` no, y eso también está comprobado.
- `mrpg -p startup` deja el ORPG sin rastro del job anterior. Se prueba encadenando dos sitios
  distintos y comprobando que no se cuela ningún producto del primero.
- MetPy decodifica el fichero de `nbtcp` igual que el del feed de Unidata.
- **Equivalencia**: elegir un KAMX reciente donde existan a la vez Level II en AWS y Level III
  en el bucket de Unidata; pasar el mismo volumen por las dos vías y comparar. Es la validación
  cuantitativa de toda la cadena. Herramienta y lado de referencia ya hechos:
  `f0/equivalencia.py`. Buscar la pareja tampoco cuesta nada —los 302 volúmenes de KAMX del
  2026-11-01 tienen su Level III con el mismo sello de tiempo—, ver
  [Catálogo verificado](../referencia/catalogo-verificado.md).
- **Velocidad**: los mismos volúmenes por `-T`, sin `-T` y `-m`, con los productos comparados
  entre sí. Si son idénticos, el demo deja de costar hora y media por job.
- **Integridad**: ningún producto truncado (`f0/integridad.py`) en ninguno de los tres modos.
  Primera pasada, con `LR=100000`: 4 de 7 N0B truncados. Ver D11.
- Las medidas de recursos de [Límites y recursos](../operacion/limites-recursos.md).

Nada de lo que sigue se escribe hasta que esto pase.

## F1 — Runner ejecutable

Reproducción con `play_a2 -m -d` (D6). Imagen `job-runner` (ORPG + pipeline) y un CLI que ejecuta un job completo desde una lista de
claves, sin cola ni API. Configuración de `nbtcp` y RPS list horneadas en la imagen, con `LR`
alto (D11). El CLI filtra los ficheros que no son productos (`GSM…`, `P173_…`), pasa
`integridad.py` antes de decodificar y le da a `l3proc watch` una copia, porque lo consume.

**Puerta (D12, 2026-11-03):** doce volúmenes de un huracán entran y salen como COGs en disco,
con el `vol_time` correcto y la georreferenciación correcta. Postgres y R2 pasan a F2.

**Estado (2026-11-04): F1 cerrada, también con el pipeline de `main`.** La puerta se pasó en `orpg-f0` y se repitió dentro de la
imagen `job-runner:f1` (`job-runner/Dockerfile`): doce volúmenes de Irma, 106 productos
enteros, 70 COGs y 36 JSON, `vol_time` y coordenadas correctos, 83 min, idéntico a la corrida
de `orpg-f0` ([Hechos verificados](../referencia/orpg-hechos.md#la-puerta-de-f1-dentro-de-la-imagen-job-runnerf1-2026-11-04)).

## F2 — Jobs como servicio

Schema de control (tokens, niveles, jobs, entradas), cola con `FOR UPDATE SKIP LOCKED`,
`jobs-api` con alta de job y estado, almacenes demo creados, creación y borrado de schemas y
roles por job, `jobs-admin issue` para emitir tokens.

**Puerta:** dos jobs seguidos, lanzados por API, sin interferencia entre ellos; un job
cancelado a mitad no deja schema, rol ni objetos huérfanos.

**Tanda de desgaste (movida desde F1, 2026-11-04):** de 10 a 15 jobs cortos (1 volumen) seguidos
en el mismo contenedor, alternando sitios en las dos direcciones (KAMX ↔ KHGX), midiendo tras
cada uno memoria de `mrpg`/`owr_server`, número de procesos y coordenadas de los productos. F1
solo probó dos jobs en una dirección ([Hechos verificados](../referencia/orpg-hechos.md#dos-jobs-seguidos-en-el-mismo-contenedor-2026-11-04));
lo que esta tanda busca es lo que se acumula con el reciclado (D3), que con dos jobs no se ve.
Se corre con el runner ya detrás de la cola, no a mano.

**Estado (2026-11-05): F2 cerrada en un entorno de desarrollo** (Postgres propio y S3 simulado, no R2 ni el
Swarm). La puerta se pasó con el ORPG real —cancelación a los 30 s sin restos, dos jobs KAMX y KHGX a la
vez sin interferencia— y la tanda de desgaste (12 jobs, ↔) pasó entera. Detalle, límites y lo que **no**
está probado: [Resultados de F2](../referencia/f2-resultados.md). Decisiones nuevas: D13, D14, D15.

## F3 — Viewer demo

Segunda instancia del `lamula-webviewer`: resolución de credenciales por token de resultado,
línea de tiempo inicializada en la ventana del job, pantalla de estado, capas de viento y
rayos ocultas en jobs históricos.

**Puerta:** un enlace abierto **mientras** el job corre muestra los productos apareciendo.

**Estado (2026-11-05):** el requisito previo, publicar por lotes durante el job, está hecho (D17): el primer
producto aparece a los 80 s y las filas crecen en 8 pasos.

**Viewer (2026-11-05), rama `f3-demo-jobs` de `lamula-webviewer`, sin commitear ni fusionar:** credenciales por token
(cookie `lamula_job` → `GET /v1/results/<token>` de `jobs-api`), pantalla `/j/<token>` que sondea el estado y abre
el visor al llegar el primer lote, desalojo LRU de pools (`MAX_POOLS=20`), viento y rayos ocultos con
`NUXT_PUBLIC_DEMO_JOB=true` (y 404 en `/api/wind|lightning/times` con `NUXT_JOBS_API_URL`). La línea de
tiempo cae en la ventana del job porque `last_seen_at = vol_to` (`worker.py`). 713 pruebas unitarias, lint y
typecheck pasan. **Puerta pasada en desarrollo (2026-11-05):** enlace abierto con un job real corriendo y el visor
avanzó solo al segundo volumen, sin recargar ([Resultados](../referencia/f2-resultados.md#viewer-demo-con-un-job-real-2026-11-05)).
Falta R2/Swarm reales y el viewer de producción.

## F4 — Selector y casos preparados

Catálogo de sitios y días desde `jobs-api`, selección de rango, estimación de duración, menú de
huracanes conocidos, página pública con el formulario de solicitud y Turnstile.

**Estado (2026-11-06):** hecho el catálogo de `jobs-api` (`/v1/catalog/*`: sitios, volúmenes, casos) y el alta desde la fuente
pública (D18). Selector `/demo` en el viewer (rama `f3-demo-jobs`).
**D19 (2026-11-06):** los casos preparados se procesan una vez, sin token, en base y bucket aparte; hecho el backend
(`destino='casos'`, `jobs-admin caso`, worker por destino). Hecho el etiquetado "no oficial" del visor (`NUXT_PUBLIC_DEMO_JOB=true`). Hecho el backend de solicitudes con aprobación por correo (D20). Hecho el formulario en `/demo` del viewer. Falta desplegar la instancia del viewer de casos y operar D20
(Brevo, subdominio, Turnstile). **D18 probada con el ORPG real (2026-11-07):** 2 volúmenes de KAMX (2017-09-10 15:04 y 15:11 UTC) bajados del bucket
público de Unidata dentro del worker, `ready` en 966 s (16 min), primer lote a los 92 s. En la base: `radars` con
`AMX` en 25,611 / -80,413 (las coordenadas reales de KAMX), 6 rasters (N0B ×2, N0G ×2, DVL ×1, EET ×1), 7 productos y 72
fenómenos; `jobs-admin orphans` limpio. **D19 probada con el ORPG real (2026-11-07):** el caso Harvey (KHGX, 17 volúmenes) en una `lamula_casos` y un bucket de casos locales, `ready` en 91 min, `expires_at` nulo; `radars` HGX 29,472 / -95,079, 99 rasters (12:04:16 a 13:29:17), 9 productos, 1555 fenómenos; 99 objetos en el bucket de casos y ninguno nuevo en el de jobs normales; `GET /v1/public/cases` lo lista sin token. Un caso fallido no bloquea repetirlo. **Viewer sobre `lamula_casos` (2026-11-07):** instancia con credenciales estáticas (`NUXT_PG_*`, sin `NUXT_JOBS_API_URL`) y `NUXT_PUBLIC_DEMO_JOB=true`; `/HGX/153/20170827T123000` abre Harvey con la etiqueta «no oficial», el COG responde 200 y el radar cae en la costa de Texas. Dos hallazgos, **corregidos y comprobados en navegador (2026-11-08, `lamula-webviewer` `54ab0b8`)**: `migrate-feedback` ya no crea el schema `viewer` con `NUXT_PUBLIC_DEMO_JOB=true` (borrado a mano y no reaparece al arrancar), y la instancia de casos lleva `NUXT_PUBLIC_CASOS_ONLY=true`, que oculta «EN VIVO» y apaga el refresco (la instancia de jobs no la lleva: lo necesita). «hace 9 años» es la insignia de frescura y es correcta en un caso histórico; la línea de tiempo muestra una ventana de animación anclada en la hora elegida (12:09–13:08 UTC), no un corte de datos. **Clic desde `/demo` probado (2026-11-08):** una instancia de jobs (`NUXT_JOBS_API_URL`, `NUXT_PUBLIC_CASOS_URL`) lista Harvey desde `/v1/public/cases`; el clic abre la instancia de casos en `/HGX/153/20170827T120416`, con la etiqueta «no oficial», sin «EN VIVO», sin errores de red y con el radar dibujado. Ojo: el enlace usa el producto 153 fijo y la hora `desde` del caso (12:04:16 UTC), y el visor abrió en 12:09:25 UTC, el primer fotograma de ese producto. **Segundo caso y convergencia (2026-11-08):** Irma (KAMX) falló al terminar porque la base de casos es compartida y `verificar_coordenadas` exigía una sola fila en `radars` (y el `UPDATE … last_seen_at` pisaba las filas ajenas); corregido en `worker.py` (solo la fila del sitio del job) con test. El intento fallido dejó datos parciales; repetido el caso (el fallido no bloquea), llegó a `ready` con 75 rasters, 75 `r2_key` distintas y 75 objetos en el bucket, sin duplicados. Harvey intacto (99/99/99, `last_seen_at` propio). **Radar compartido (2026-11-08):** Milton (KTBW, 2024) `ready` en 1 h 37 min con 84 rasters, 84 objetos, `radars` TBW con su `last_seen_at`; Irma y Harvey intactos. **Ian (KTBW, 2022) falla** a los 3 min: `grid_radial` del pipeline lanza `ValueError` con un N0G de 720 radiales y azimuts con jitter (719 bins únicos), también con el producto original de Unidata; reportado en [nexrad-l3-pipeline#11](https://github.com/vladimir1284/nexrad-l3-pipeline/issues/11), sin tocar ese repo. Un producto malo tumba el caso entero (`l3proc` sale con código ≠ 0). **Michael (KEVX, 2018) `ready` (2026-11-08):** 102 rasters en EVX, sin tocar AMX 75, HGX 99, TBW 84. **Ian (KTBW, 2022) `ready` (2026-11-08)** tras corregirse #11 (pipeline `534d75f` y `ad8814c`, revisados leyendo el diff): imagen `job-runner:f4` con el pipeline en `ad8814c`, 5369 s, 77 rasters nuevos en TBW (161 con Milton), ningún aviso de «hueco de» en el log. **Cinco casos publicados.** Fallo hallado y corregido: en radar compartido cada caso pisaba `radars.last_seen_at` con su propio final y quedó TBW en 2022 en vez de 2024; ahora `fijar_last_seen` usa `GREATEST` en base compartida, con test (la fila local se corrigió a mano; el worker en marcha no lleva aún el arreglo). No probado: los casos Irma, Milton, Michael e Ian en el visor, el recuento de objetos en el bucket de Michael e Ian, ni un fallo forzado a mitad de job. Hay que reconstruir `job-runner` con el código actual antes de desplegar.

**Puerta:** alguien ajeno al equipo completa el camino entero sin ayuda: pide acceso, recibe
token, lanza un caso preparado y abre el resultado.

## F5 — Operación

Cron de expiración, cuotas aplicadas de verdad, logs por job en R2, métricas (duración, tasa
de fallo, ocupación de la cola), alerta cuando un job lleva demasiado tiempo reclamado, y la
decisión definitiva sobre la ventana de ejecución según lo que haya mostrado la contención
real.

**Puerta:** una semana con jobs reales sin intervención manual y sin retraso medible en el
pipeline live.

## Fuera de alcance por ahora

- Subida de ficheros del cliente (llega con la herramienta de conversión a Level II).
- Productos que el feed público no distribuye pero el ORPG sí genera: HI (59), TVS (61), SS
  (62). El parser del pipeline no los lee. Es un diferenciador claro frente al demo live, y un
  candidato a fase propia más adelante. Matiz comprobado el 2026-11-02: **MetPy ya tiene los
  tres en su tabla de productos**, así que los abre y expone sus bloques; lo que falta en
  nuestro lado es el mapeo a registros de `phenomena`, del tamaño de los que ya existen para
  NST y NMD, no un decodificador desde cero.
- Mosaico multi-radar en jobs: un job es de un solo radar.
- Capas de viento y rayos históricas (GFS y GLM archivados).
