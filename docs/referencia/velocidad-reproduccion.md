# Velocidad de reproducción (medida de D6)

Medida del 2026-11-02, KAMX, 12 volúmenes de Irma (2017-09-10 17:02 a 18:17 UTC, 246 MB), en el
contenedor `orpg-f0` (imagen `orpg-prod:b24`). Reproducible con `f0-run/run_modes.sh`,
`f0-run/run_one.sh`, `f0/integridad.py`, `f0/coordenadas.py` y `f0/equivalencia.py`.

| Modo | Enlace (`LR`) | Duración | Ficheros | Productos válidos | N0B truncados |
|---|---|---|---|---|---|
| `-m` | 100 000 | 4 670 s (78 min) | 127 | — | **8 de 12** |
| `-T` | 1 536 000 | 4 903 s (82 min) | 132 | 106 | 0 |
| sin `-T` | 1 536 000 | 4 808 s (80 min) | 131 | 106 | 0 |
| `-m` (`m2`) | 1 536 000 | 4 662 s (78 min) | 132 | 106 | 0 |

La fila `-m` con `LR=100000` **no es comparable**: sus N0B salieron truncados (ver D11). Se
repite como `m2` con el enlace corregido.

## Lo que dicen los números

- **Los tres modos producen productos iguales**: `f0/equivalencia.py comparar` de `-T` contra
  sin `-T` y de `-T` contra `m2`, 106 huellas cada vez, tolerancia 0,1 %, 0 diferencias en DAA,
  DTA, DVL, EET, N0B, N0G, NMD, NST y NVW.
- **Los tres modos duran lo mismo, 78 a 82 min** (con enlace bueno, 4 662 a 4 903 s), con una
  diferencia del 5 % entre el más lento
  y el más rápido. Es decir, **el reloj de `play_a2` no es el cuello de botella**: el ORPG tarda
  unos 6,5 min por volumen en procesar KAMX (VCP 212, 21 MB), pase lo que pase con el ritmo de
  entrada. Perfilado después: el ORPG **espera, no calcula**, por el control de flujo de `play_a2 -m` (ver [Perfil del ORPG](perfil-orpg.md)).
- **Decisión del dueño (2026-11-02), D6:** se usa el modo más rápido si no afecta a los
  resultados, es decir `-m`. No recorta el coste de un job de forma apreciable y no cambia los
  productos. El demo sigue costando ~6,5 min por volumen de KAMX, y las cuotas de D8 se calculan
  con eso, no con la duración del volumen.

## Qué falta para cerrar

Una sola repetición por modo: la variación entre corridas del mismo modo no está medida. Y el
perfil de qué tarda en el ORPG si se quiere recortar el coste (ver
[Límites y recursos](../operacion/limites-recursos.md)).
