# Medidas crudas

La salida literal de las medidas que citan las páginas de `docs/referencia/`. Están aquí para
que un número no dependa de la memoria de una sesión: si alguien discute una cifra, esto es lo
que se midió y con qué.

| Fichero | Qué es | Cómo se regenera |
|---|---|---|
| `2026-11-02-ventanas-6h.txt` | Volúmenes, bytes, cadencia y VCP de las cinco ventanas de 6 h que se probaron primero | `f0/catalogo.py cases --vcp` |
| `2026-11-02-intensidad-casos.txt` | Perfil de eco de los cinco casos: máximo dBZ y porcentaje de área fuerte, hora a hora | `f0/intensidad.py` |
| `2026-11-02-intensidad-harvey-27.txt` | El mismo perfil para KHGX el **27** de agosto, el día que resultó ser el bueno | `f0/intensidad.py KHGX 2017-08-27` |

De estas medidas salieron las ventanas de hora y media que hay en
[Catálogo verificado](../../docs/referencia/catalogo-verificado.md). Las de 6 h quedan como
evidencia de por qué se descartaron: a `-T` son casi seis horas de nodo por job.

`vcp_vs_tamano.py` es el script de un hallazgo que no tiene herramienta propia: el tamaño del
fichero sigue al patrón de barrido, no a la tormenta.
