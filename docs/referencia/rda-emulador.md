# Emulador de RDA como alternativa a `play_a2` (2026-11-03)

**Resultado: no hay ganancia demostrada. D6 no cambia.** Se probó si alimentar el ORPG como si fuera
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

## Conclusión

Sin control de flujo el ORPG no es fiable; con el ritmo de `LR=1536000` apenas se gana y los productos
no coinciden con los de `play_a2 -m`. Cambiar el camino de ingesta cuesta una validación de
equivalencia completa para un beneficio no demostrado. Queda sin responder qué falla a ≥4×.
El contenedor se dejó con la configuración `player` original y parado.
