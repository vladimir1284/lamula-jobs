# Dónde se van los 6,5 minutos por volumen

Medida del 2026-11-02, KAMX, 2 volúmenes de Irma (17:02 y 17:09 UTC), `play_a2 -m -d`, enlace con
`LR` alto, contenedor `orpg-f0`. Reproducible con `f0/perfil.sh` (muestrea `/proc` cada 2 s) y
`f0/perfil.py` (resumen). Pregunta: si el reloj de `play_a2` no es el cuello de botella
([Velocidad de reproducción](velocidad-reproduccion.md)), ¿qué lo es?

## Resultado

**No es cómputo: el ORPG espera.** Los dos volúmenes tardaron 745 s con `-m` (unos 6 min por
volumen, igual que en la corrida de 12) y los procesos del ORPG sumaron del orden de 30 s de CPU
en 865 s de ventana, muy lejos de los 4 núcleos disponibles.

*Matiz de la medida:* el muestreador suma solo los procesos vivos en cada instante, así que
subestima los que terminan, y el contador `bash` (68 s) es el propio muestreador. La conclusión
«espera, no cómputo» no descansa en esa suma sino en los tiempos de salida de los productos y en
el fuente (abajo). Lo que sí está medido: el proceso que más CPU gastó, `veldeal`, usó 8 s.

**Tiempos de salida** (mtime de los ficheros de `nbtcp`, hora del contenedor):

| Instante | Qué sale |
|---|---|
| 02:48:08 y 02:48:20 | N0B y N0G del volumen 1: el primer corte llega enseguida |
| 02:53:57 – 02:54:01 | NVW, DVL, EET, NST, NMD del volumen 1: **5 min 50 s** después |
| 02:54:24 y 02:54:53 | N0B y N0G del volumen 2 |
| 03:00:26 – 03:00:34 | DAA, DTA, DVL, NVW, EET, NST, NMD del volumen 2: otros ~6 min |

El ritmo lo marca la alimentación del volumen, no el cálculo posterior: cuando acaba el último
corte, los productos de fin de volumen salen en segundos.

## Por qué: el control de flujo de `-m`

En `pa_playback.c` (`PAP_handle_max_speed`), antes de escribir cada radial `play_a2 -m` duerme
**1 ms**, y **30 ms si hay más de 1500 radiales sin confirmar**. La confirmación llega del propio
RPG, por evento (7087), cuando termina un corte. Con volúmenes de ~8000 radiales y confirmaciones
que llegan por cortes, el emisor pasa la mayor parte del tiempo en el tramo de 30 ms.
*Inferencia, no medida:* no se contaron los radiales ni las veces que entró en cada tramo; el
orden de magnitud (8000 × 30 ms ≈ 4 min) es compatible con lo observado pero no lo demuestra.

Consecuencias, también inferidas:

- `-m` no puede ir más rápido sin cambiar `play_a2` o el RPG. **No se toca el build** (AGENTS.md).
- El coste de un job es ~6 min por volumen de KAMX **con la CPU casi libre**. Mientras corre, el
  ORPG deja casi todo el nodo a otros usos, lo que juega a favor de D7 (mismo nodo que producción),
  pero eso hay que medirlo con el pipeline live en el nodo, no se deduce de aquí.
- Dos jobs a la vez en el mismo ORPG no es posible (D3), pero sí podría haber **dos ORPG**
  (dos runners) sin que el cómputo sea la limitación. Es una pregunta para F2, no una decisión.

## Qué falta

Contar radiales y confirmaciones para confirmar el mecanismo; repetir con otro VCP (los 6,5 min son
de VCP 212) y con un sitio de menos radiales.
