# Resultados de F2 (2026-11-04/05)

Qué se midió, con qué y qué **no** se midió. Runbook en [F2 en una máquina con Docker](../implementacion/f2-ejecucion.md);
el código en `jobs/`. Las trazas de las corridas (no versionadas) quedaron en `f0-run/f2-gate.log` y
`f0-run/f2-desgaste.log`.

!!! warning "Qué es y qué no es este entorno"
    Postgres 16 propio (`lamula-pg-f2`) y un **S3 simulado (moto)** en lugar de R2: no hay credenciales
    ni bucket demo. El código del pipeline que publica es el real (`main`, `175bf0c`) y habla S3 por
    endpoint, pero **nada de esto se probó contra R2**: ni CORS, ni hostname, ni límites, ni latencia.
    Tampoco contra el Postgres de producción ni con el Swarm.

## Puerta de F2, con el ORPG de verdad

Orquestada por `jobs/e2e/gate.py`, todo por la API (alta, cancelación, estado):

| Comprobación | Resultado |
|---|---|
| Cancelar un job con `play_a2` reproduciendo | Estado `cancelled` **30 s** después de pedirlo |
| Procesos del ORPG tras cancelar | `play_a2`, `nbtcp`, `mrpg`: 0, 0, 0 |
| Directorio de trabajo del job | Borrado |
| Schema, roles `job_<id>` y `job_<id>_ro` tras el barrido | No existen; `huérfanos` idéntico al de antes de empezar |
| Dos jobs lanzados a la vez, KAMX y KHGX | Los dos `ready`, en serie (concurrencia 1) |
| `radars` de cada schema | Una fila: `AMX 25.611 -80.413` y `HGX 29.472 -95.079`; `last_seen_at` = hora del último volumen |
| `rasters` de cada schema | Solo su sitio (3 y 4 filas); en el bucket, prefijos `AMX/` y `HGX/` y nada más |

## Tanda de desgaste (la que F1 dejó para aquí)

12 jobs de un volumen, seguidos, alternando KAMX ↔ KHGX en el mismo contenedor, **detrás de la cola**
(`jobs/e2e/desgaste.py`). Tras cada job se caduca y se barre, de modo que el borrado de schema, roles y
objetos también se ejerció 12 veces.

| Medida | Resultado |
|---|---|
| Jobs `ready` / con coordenadas correctas / con solo su sitio en el schema | 12 / 12 / 12 |
| Duración | KAMX 570–635 s (media ~590), KHGX 495–515 s |
| Procesos en el contenedor tras cada job | 7, constantes (entrypoint, `rssd`, `sleep`, `bash`, el worker, `nds`, `owr_server`) |
| `owr_server` (RSS) | 4,8–5,1 MiB, sin tendencia |
| RSS del resto sin el worker | 16,5–17,2 MiB, sin tendencia |
| `play_a2`, `nbtcp`, `mrpg` vivos tras cada job | 0, 0, 0 en los 12 |
| Al final: schemas y roles huérfanos / objetos en el bucket | 0 / 0 |

**Lo que esto prueba y lo que no.** El reciclado (D3: `mrpg -p startup` + `change_radar`) no acumula
procesos ni memoria residente entre jobs, y no deja un sitio en el siguiente en ninguna de las dos
direcciones, en 12 vueltas. **No prueba** el comportamiento de `mrpg` *durante* un job largo: la foto se toma
al terminar cada job, con el ORPG ya cerrado, así que la memoria que `mrpg` y sus 107 tareas usan mientras
trabajan no está medida aquí (sigue siendo el pico de un volumen de F0: 125 % de CPU, 790 MiB). Y son jobs
de **un** volumen: un job de doce se parece más al coste de F1 (83 min) y no se ha repetido en cadena.

## Lo que se encontró

1. **El `ENTRYPOINT` de la imagen ignora el comando** y arranca el ORPG en `sleep infinity`. Un worker
   pasado como `CMD` no corre y el job se queda en la cola sin error. Pendiente de decidir cómo se supervisa.
2. **`nbtcp` escribe `nbtcp.log.<puerto>` en el directorio de trabajo.** Lanzado desde un directorio sin
   permiso de escritura, `nbtcp` sale con 255 (`Unable to create nbtcp.log.4491 (Permission denied)`). El
   worker lanza cada subproceso con el cwd en el directorio del job.
3. **Los roles de Postgres son del clúster, no de la base.** `DROP DATABASE` no se los lleva, y un
   comprobador de huérfanos que mire roles ve los de otras bases del mismo servidor. Con una sola base por
   servidor (el plan) no pasa; en las pruebas, sí pasó, y un teardown demasiado ancho estuvo a punto de
   borrar roles ajenos.
4. **`DROP OWNED BY` falla en PG16** para el creador de un rol (hay que ser miembro). No hace falta: los roles
   de job no son dueños de nada, y sus permisos se van con el schema.
5. **Dos jobs del mismo radar y hora se pisan en el bucket** (las claves del pipeline no llevan job). Ver D14.
6. **`radars.icao` queda `NULL`** en lo que publica el pipeline para estos sitios. El worker lo tolera y
   comprueba `site_id` y lat/lon; si el viewer necesita `icao`, es del pipeline.

## Margen del timeout de runner muerto (2026-11-05)

Un job de 12 volúmenes de Irma (KAMX, `play_a2 -m -d`) por la cola real, con el ORPG real y el worker bajo
`jobs-supervisor`, y `now() - heartbeat_at` muestreado cada 2 s durante todo el job. Script:
`jobs/e2e/timeout_runner.py`.

| Medida | Valor |
|---|---|
| Duración del job (`queued` → `ready`) | 5055 s (84 min), intento 1, sin error |
| Muestras de latido | 2523 |
| Hueco entre latidos: mediana / p99 / **máximo** | 5,2 s / 9,7 s / **13,2 s** |
| Huecos de más de 30 s | 0 |
| Timeout del barrido durante la medida | 600 s, 45 veces el máximo observado |
| Tope del paso del runner (`n*12*60+1800`) | 10440 s, 2,1 veces la duración real |
| Schemas y roles huérfanos, antes y después | ninguno |

**Qué dice y qué no.** El hilo de latido aguanta una hora y media con el ORPG a pleno sin un solo hueco
relevante, así que 600 s no producía falsos positivos: ningún job sano habría sido reclamado. Era margen de
sobra, y por eso se bajó a **120 s** el mismo día ([D16](../alcance/decisiones.md#d16-un-runner-sin-latido-durante-120-s-se-da-por-muerto-2026-11-05)).

**Lo que no cubre:** un solo job y una sola corrida; solo KAMX; el hilo de latido bajo la carga de **un**
job (no con el pipeline live compartiendo nodo, que sigue sin medirse); y el coste del timeout largo no se
ha tocado: con un worker muerto, el ORPG huérfano sigue reproduciendo hasta que el timeout reclama el job (ver el runbook de F2).
Bajar el timeout a 120 s (9 veces el máximo) lo recorta a ~2 min. Con contención en el nodo el hueco puede
crecer: D16 dice cuándo revisarlo.

## Lo que F2 **no** hace todavía

- **No publica mientras el job corre.** El runner reproduce todo, filtra por integridad (D11) y *después*
  llama a `l3proc watch --once`. El enlace de resultado funcionaría cuando el job está `ready`, no
  «mientras» (D6). Es **el** requisito de la puerta de F3 y exige publicar por lotes durante la reproducción.
- **No lista ni descarga el catálogo de AWS** (D10): `jobs-api` acepta claves ya en staging. El selector es F4.
- **El bucket R2 y la base `lamula_demo` de verdad no existen**: hacen falta credenciales del dueño.
- **El cron del barrido no está programado**: `jobs-admin sweep` existe y está probado, falta quien lo llame.
- **Cuota en bytes (`max_bytes`)**: la columna existe, está validada en el alta y sin valor en ningún nivel.
