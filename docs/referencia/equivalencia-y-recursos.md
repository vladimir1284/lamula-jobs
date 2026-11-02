# Equivalencia contra el feed oficial y recursos (F0)

Medidas del 2026-11-02. Reproducibles con `f0-run/run_ref.sh`, `f0/equivalencia.py` y
`docker stats` (muestras cada 10 s en `f0-run/stats-ref.csv`, que no entra al repo).

## Equivalencia: un volumen de KAMX, 2026-11-01 00:13:20 UTC

El mismo barrido por las dos vías: el Level III que distribuye Unidata y el que genera nuestro
ORPG a partir del Level II de ese volumen. Tolerancia 0,1 %.

| Producto | Resultado |
|---|---|
| N0B (reflectividad) | **igual** |
| EET (ecos tope) | **igual** |
| DVL (VIL) | **igual** |
| NMD (mesociclones) | **igual** |
| N0G (velocidad) | máximo 49,0 frente a 47,5 (3,1 %), suma 1,3 % |
| DAA, DTA (acumulaciones) | distintos: p50 un 73 % menor, suma un 94 a 99,6 % menor |
| NST (tormentas) | mismas 24 celdas, **identificadores distintos** (`A1, A7…` frente a `A0, B0…`) |
| NVW (viento vertical) | 12 niveles frente a 13 |
| DU3 | no salió (la petición 173 devuelve un fichero de estado, no un producto) |

**Lo que sí está medido:** los cuatro primeros son iguales, y son los que no dependen de otros
volúmenes. **Inferencia, sin probar:** las diferencias de DAA, DTA, NST y NVW son de *historia*.
El feed oficial lleva horas de acumulación y de seguimiento de tormentas, y el ORPG de F0
arrancó en frío con un volumen (`mrpg -p startup` limpia los almacenes). Si es así, un job de
doce volúmenes converge hacia el oficial a medida que acumula, y un job de un volumen no lo hará.
La prueba que falta: reproducir los volúmenes previos al de referencia y comprobar que DAA, NST
y NVW se acercan. N0G (3 %) no encaja con esa explicación y queda sin causa conocida.

**Para el producto:** un demo de pocos volúmenes mostrará acumulaciones y tormentas que **no
coinciden con las oficiales**, y eso es correcto, no un fallo. Conviene decirlo en el viewer.

## Recursos

Un volumen reciente (6,7 MB, `-m`, 224 s) con muestras cada 10 s:

| Medida | Valor |
|---|---|
| CPU media / pico | 19,8 % / 125 % (de 4 núcleos: un núcleo y cuarto) |
| Memoria pico | 790 MiB |
| Duración | 224 s para un volumen de 6,7 MB |

Doce volúmenes de Irma (21 MB cada uno), con el ORPG ya arrancado:

| Medida | Valor |
|---|---|
| Duración | 4 662 a 4 903 s según el modo, unos 6,5 min por volumen |
| Productos crudos | 11 MB |
| COGs y JSON decodificados | 53 MB |

El tiempo por volumen depende del volumen: 224 s para uno de 6,7 MB frente a ~390 s para los de
21 MB de Irma. Sin la medida del pipeline live corriendo en el mismo nodo (pendiente: aún no se
midió el retraso del `processor`), el pico de CPU de un job es un núcleo y cuarto.

## Aislamiento entre jobs (puerta de D3)

KAMX (Irma, 12 volúmenes, tres modos y la referencia) y después, en el **mismo contenedor y con
solo `change_radar -r khgx -S -R` más `mrpg -p -v startup` entre medias**, dos volúmenes de
KHGX del 2026-11-01 (16:21 y 16:28 UTC, 583 s):

| Comprobación | Resultado |
|---|---|
| Productos de KHGX | 18 (9 tipos × 2), 0 truncados |
| Coordenadas | los 18 con `siteID=HGX`, `lat=29.472`, `lon=-95.079` |
| Control negativo: los mismos 18 contra KAMX | los 18 rechazados |
| Ficheros con `AMX` en el nombre, o fechas de 2017 | 0 |

**Pasa.** Límites de la prueba: un solo cambio de sitio, en una dirección (KAMX → KHGX), y cada
pasada escribe en un directorio nuevo, así que lo que se comprueba es que el ORPG no emite
productos del sitio anterior, no que el sistema de ficheros esté limpio. Una primera corrida
sin volúmenes (el catálogo de KHGX del 2026-11-01 empieza a las 16:21) no probó nada y se
descartó; `catalogo.py fetch` ahora falla si la ventana no tiene volúmenes.
