# Plan de trabajo autónomo (2026-11-02)

Plan para que la sesión avance sin el dueño del producto durante varias horas. Está en el repo
porque la próxima sesión no tiene otra memoria que esta. **Lo que queda marcado «no» no se hace
sin él**, aunque parezca la continuación natural.

## Estado de partida

Contenedor `orpg-f0` arriba (imagen local `orpg-prod:b24`), KAMX, `nbtcp` automatizado, 12
volúmenes de Irma en `f0-run/ar2in12`. Dos scripts encadenados dentro del contenedor, en este
orden, que dejan una línea por pasada en `/home/orpg/resumen.txt`:

1. `f0-run/run_modes.sh`: `-m` (enlace `LR=100000`), `-T` y sin `-T` (los dos con `LR=1536000`).
   Termina con la línea `FIN`.
2. `f0-run/cola.sh`, que espera a `FIN` y lanza `f0-run/run_one.sh m2 "-m"`: la pasada `-m`
   repetida con el enlace corregido. Termina con `FIN-m2`.

Duración estimada de todo: unas 4 h desde las 08:30 hora del portátil. **Si `resumen.txt` no
avanza en 30 min, mirar `ps` y los `modo-*.out` antes de lanzar nada.**

## Orden de trabajo

**Hechos (2026-11-02):** pasos 1 a 6 y 8 (recursos de un solo volumen). Ver [Velocidad de reproducción](../referencia/velocidad-reproduccion.md).
Quedan 6, 7 y 8, con el ORPG ya libre.

| # | Cuándo | Qué | Entrega |
|---|---|---|---|
| 1 | Al acabar `-m` | `integridad.py` sobre `products-m`. Es la línea base del fallo. | Número de truncados |
| 2 | Al acabar `-T` | `integridad.py` sobre `products-T`. **Confirma o descarta la hipótesis del enlace** (D11). | D11 se confirma o se reescribe, commit |
| 3 | Al acabar `-T` | Decodificar `products-T` completo (copia, `--no-publish`), contar fallos que no sean `GSM`/`P173`. | Tabla de fallos en `orpg-hechos.md` |
| 4 | Al acabar `none` | Lo mismo que 1 y 3. | Idem |
| 5 | Al acabar `m2` | `equivalencia.py huella` de los tres modos con enlace bueno (`T`, `none`, `m2`) y `comparar`. **Es la medida de D6.** | Duraciones e igualdad, en `docs/referencia/` con fecha |
| 6 | Con `products-T` | Equivalencia contra el feed oficial **no es posible con Irma** (el archivo L3 acaba en marzo de 2022). Bajar un KAMX reciente con `catalogo.py pairs` y pasarlo por el contenedor al final, con el ORPG ya libre. | Resultado de la puerta de equivalencia |
| 7 | Con el ORPG libre | Aislamiento: `change_radar -r khgx`, `mrpg -p -v startup`, 2 volúmenes de KHGX, comprobar que no hay un solo producto de KAMX y que el `lat`/`lon` es el de KHGX. | Puerta de D3 |
| 8 | Con el ORPG libre | Medidas de recursos con `docker stats` durante una pasada. | Números para `limites-recursos.md` |
| 9 | Siempre | Un commit por resultado, `git push`. Un borrador de LinkedIn solo si el hallazgo cambia algo del diseño. | `linkedin/NN-…` |

La comprobación de que el `lat`/`lon` dentro de los productos es el del sitio (puerta del paso
3 de F0) no tiene herramienta todavía: `wmo_probe.py` solo lee del bucket. Escribirla como
`f0/coordenadas.py` (lee un fichero local con MetPy y compara con el sitio esperado) es parte
del paso 7 y de la regla «las coordenadas se verifican».

## Reglas de parada

- Si una pasada falla por motivos del contenedor (ORPG sin arrancar, `nbtcp` sin conectar), un
  reintento; si falla otra vez, se anota el síntoma en `pendientes.md` y se pasa al siguiente
  paso, no se rediseña.
- Si el espacio libre baja de 5 GB (`df -h /`), se borran `f0-run/products-*` ya analizados,
  nunca los volúmenes de `ar2in12`.
- Si un resultado contradice una decisión congelada, **se documenta y se para ahí**: ninguna
  decisión se revierte en solitario. D6 en particular se re-decide con el dueño, aunque la
  medida salga clara.

## Lo que no se hace sin el dueño del producto

- **No** enviar los correos de `correspondencia/` ni publicar nada de `linkedin/`.
- **No** tocar el build del ORPG ni compartir la imagen (licencia).
- **No** tocar `orpg-prod` ni `rocky8-radar-dev`, que son de otro trabajo y están corriendo.
- **No** escribir código del servicio (runner, cola, API) hasta que F0 pase entera.
- **No** modificar `nexrad-l3-pipeline` ni abrir issues en él: se propone en `pendientes.md`.
- **No** `git push --force`, ni reescribir historia.

## Cuando termine todo

Redactar el estado de F0 al principio de `AGENTS.md` (qué puertas pasaron, cuáles no, qué decide
el dueño), dejar los contenedores como están y no lanzar más pasadas.
