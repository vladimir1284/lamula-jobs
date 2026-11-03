# Emulador de RDA como alternativa a `play_a2` (2026-11-03)

**Resultado inicial: sin ganancia a 1×. Actualización al final: con búferes mayores el 4× funciona a veces, sin ser fiable. D6 no cambia.** Se probó si alimentar el ORPG como si fuera
un radar real (línea de banda ancha por `cm_tcp`) es más rápido que `play_a2 -m`.

## Qué se probó

El repo `vladimir1284/RDA_Backend` es un emulador de RDA para observaciones `.obs` de Vesta
(radares cubanos): no lee Level II y está atado a VCP 71/72, 360 radiales por corte y rutas fijas.
Se tomó solo la idea. Un volumen Archive II ya es una secuencia de mensajes del RDA (tipos 2, 3, 5,
13, 15, 18 y 31), así que `f0/rda_replay.py` los manda tal cual, sin recodificar. El ORPG se
conecta como cliente (`tcp.conf`, enlace 0, puerto 10010, host `rda1`) con el enlace 0 de
`comms_link.conf` en `cm_tcp` en vez de `player`. `f0/rda_lr.sh` repite la pasada con una velocidad
de línea (`LR`) dada.

## Hechos medidos (2 volúmenes de KAMX, VCP 212, 12600 radiales y 67,9 MB cada uno)

| Configuración | Envío, 2 volúmenes | Productos |
|---|---|---|
| `play_a2 -m` (referencia, `perfil-orpg.md`) | 745 s | 16 |
| Emulador, `LR=1536000` (el valor de D11) | 663–704 s (≈350 s por volumen) | 18 |
| `LR=100000000` | 14 s | 0, y `pbd` registra `MESSAGE EXPIRED` |
| `LR=6144000` (4×) | 171 s | 4 |
| `LR=12288000` (8×) | 81 s | 0 |
| `LR=24576000` (16×) | 46 s | 5 |

- 67,9 MB en 350 s son 194 kB/s, el 1,55 Mbit/s de `LR`: a 1× el ritmo lo pone `cm_tcp`.
  Eso es inferencia por coincidencia numérica; el efecto de `LR` sobre el tiempo sí está medido.
- A 1× el emulador gana un 6–11 % a `play_a2 -m` (una corrida de cada, puede ser ruido).
- A 1× N0B y N0G salen iguales a los de `play_a2 -m`. En el volumen 1, DVL, EET, NVW y NMD
  difieren, y NMD/NST/DAA/DTA difieren en ids o valores: **no es equivalente**. No se investigó por qué.
- A 4× o más salen muy pocos productos y `pbd` casi no registra pérdidas (el contador dio 0 en
  la escalera). **No sé por qué faltan.** No es la causa conocida de abajo, porque en la escalera
  repetida la línea se mantuvo abierta.

## Trampas que se encontraron (útiles si se retoma)

- El acuse de login lleva `param = 20983610` (`TCM_ID`, `cmt_shared.c`); sin él, `cm_tcp` lo descarta.
- La prueba de loopback RPG→RDA (mensaje 12) exige devolver el cuerpo recibido byte a byte.
- **Si la línea se cae, `p_server` termina** (`ORPGDA_read failed … RDA_STATUS_ID`) y no se
  distribuye nada hasta reiniciar el ORPG. Cerrar la conexión al acabar el envío pierde los
  productos que el ORPG aún está generando: hay que dejarla abierta (`--linger`).
- `nbtcp` hay que arrancarlo cuando la línea ya está conectada, y el ORPG hay que reiniciarlo
  para volver a conectar `nbtcp`.

## Actualización (2026-11-03, tarde): la causa de los fallos a 4× y el techo

Hechos, de los logs del ORPG:

- A 4× o más, `veldeal` (desalias de velocidad) registra `Read Driving Input .... LB_EXPIRED` y
  aborta el volumen: `rawdata.lb` tiene `maxn_msgs = 1500` (unos 4 cortes) y se le sobrescribe.
  En una corrida `mrpg` también lo mató por `CPU Utilization 83 Too High` (límite 80), y a continuación
  `p_server` falló. El contador `MESSAGE EXPIRED` que miraba (en `pbd`) no ve esta pérdida.
- Subir `lb_n_msgs` de 1500 a 5000 en `cfg/product_attr_table` (configuración, no build) arregla el 4×:
  14 productos, idénticos a los de la corrida a 1×. El contenedor quedó con 213 MB libres de 7,8 GB
  (más 2 GB de caché) con esa configuración.

| Con búferes de 5000 | Envío, 2 volúmenes | Productos |
|---|---|---|
| 4× (`LR=6144000`), tres corridas | 173–177 s | 14, 13 y 4 |
| 8× | 84 s | 2 |
| 16× | 43 s | 7 |
| sin freno | 14 s | 0 |

- **El techo está entre 4× y 8×, y 4× no es fiable.** De tres corridas a 4× con búferes de 5000 salieron
  14 y 13 productos (en la de 13 falta NST del volumen 2 y NMD difiere) y una con solo 4
  productos y 2 `MESSAGE EXPIRED`. No sé qué distingue a esa tercera corrida de las otras. La variación entre
  corridas sin cambiar nada es en sí un hallazgo: no se puede fiar un job a este ritmo sin entender esa varianza.
- DAA y DTA no salen a 4× (sí a 1×). Sin explicar.
- Mejora medida con la corrida buena: ~175 s contra 745 s de `play_a2 -m` para 2 volúmenes.

### Volumen 1 distinto en Irma

- Las corridas de `play_a2` (tres, 2 y 12 volúmenes) dan el mismo volumen 1: DVL `suma` 297 859,
  EET 1 304 667, NVW 47 niveles. Las del emulador (1× y 4×) dan otro: 131 275, 1 567 976 y 44.
  N0B es igual. Es determinista, no ruido. Del volumen 2 en adelante coinciden.
- En el volumen de 2026-11-01 (KAMX, un volumen, arranque en frío) **`play_a2` y el emulador dan los 9
  productos idénticos entre sí**, y ambos coinciden con el feed oficial en N0B, DVL, EET y NMD.
  El defecto no es general.
- No hay referencia oficial de Irma (el bucket Level III no devolvió nada para esas horas), así que
  no sé cuál de las dos vías acierta en el volumen 1 de Irma.
- Quité el reenvío de metadatos por volumen (`--sin-metadatos`) y la corrida salió mal (4 productos),
  así que no sirve como evidencia.
- Sospecha, sin probar: un efecto de arranque en frío específico de este volumen (VCP 212) en la
  vía de banda ancha. Como las comparaciones reales necesitan historia de volúmenes de todos modos,
  un volumen de calentamiento previo podría ser la solución, pero no está probado.

## Conclusión

La causa de los fallos a 4× está identificada y tiene arreglo de configuración, pero el resultado
**no es todavía fiable** (variación entre corridas, DAA/DTA ausentes, volumen 1 de Irma distinto).
D6 no cambia. Para reabrirlo hacen falta: repetir el 4× unas 10 veces para medir la varianza,
explicar DAA/DTA y decidir qué hacer con el volumen 1. Se restauró la configuración original del
contenedor (copias `*.orig-rda` en `cfg/`), que quedó parado.
