# Lo que el pipeline espera de la salida del ORPG

Entre `nbtcp` y `l3proc process` hay un contrato que nadie escribió, porque hasta ahora los dos
extremos los ponía el mismo bucket. Esta página lo deja por escrito y documenta el primer punto
donde se rompe.

## Los diez productos

`ingest/products.py` de `nexrad-l3-pipeline` define exactamente lo que el pipeline sabe leer.
La RPS list que se le pide a `nbtcp` se recorta a esto y nada más:

| Código | Mnemónico | Qué es | Camino en el pipeline |
|---|---|---|---|
| 153 | N0B | Reflectividad super-res | raster → COG |
| 154 | N0G | Velocidad super-res | raster → COG |
| 135 | EET | Tope de ecos | raster → COG |
| 134 | DVL | VIL digital | raster → COG |
| 170 | DAA | Acumulación digital (1 h) | raster → COG |
| 173 | DU3 | Acumulación digital (3 h) | raster → COG |
| 172 | DTA | Acumulación total de tormenta | raster → COG |
| 58 | NST | Seguimiento de celdas | tabla `phenomena` |
| 141 | NMD | Detección de mesociclón | tabla `phenomena` |
| 48 | NVW | Perfil de viento VAD | tabla `vwp` |

Pedir más productos en la RPS list no rompe nada —el decodificador los rechaza con
`UnsupportedProductError`— pero gasta tiempo de ORPG y ancho del enlace NB para tirarlos.

## El fallo del encabezado WMO

!!! danger "Verificado el 2026-11-02, contra MetPy 1.7.1 y un producto real del feed"
    El pipeline saca el identificador del radar **solo** del encabezado WMO. Si `nbtcp` escribe
    el producto sin ese encabezado —que es lo que cabe esperar de un enlace Clase 1, donde el
    encabezado lo pone la distribución del NWS, no el RPG— `l3proc process` muere con
    `AttributeError` antes de escribir nada.

Los ficheros del bucket de Unidata empiezan con 30 bytes de texto:

```
SDUS52 KMFL 010000\r\r\nN0BAMX\r\r\n
```

MetPy los busca con `wmo_finder` y, si encuentra la pareja, asigna `Level3File.siteID` con los
tres últimos caracteres (`AMX`). **Si no la encuentra, no asigna nada**: el atributo no existe,
no es cadena vacía. Comprobado con el mismo producto, antes y después de quitarle esos 30
bytes:

| Fichero | `header.code` | `lat` / `lon` | `siteID` |
|---|---|---|---|
| Tal cual del bucket | 153 | 25.611 / −80.413 | `'AMX'` |
| Sin los 30 bytes | 153 | 25.611 / −80.413 | `AttributeError` |

Todo lo demás se decodifica igual. El resto del producto no depende del encabezado.

Y `siteID` no es un detalle cosmético: `radars.site_id` es la clave primaria del esquema del
pipeline, la referencia de `rasters`, `phenomena` y `vwp`, y el primer segmento de la clave de
R2 (`AMX/N0B/2026/11/01/AMX_N0B_...tif`). Sin él no se publica ni un COG.

Puntos de uso, los tres idénticos:

- `ingest/decoder/level3.py:166`
- `ingest/phenomena/parse.py:236`
- `ingest/phenomena/vwp.py:68`

### Lo que hace `nbtcp` de verdad

Leído el fuente el 2026-11-02 (`src/cpc102/tsk060/`): `nbtcp` **no añade el encabezado salvo
que se le pase `-A`**, y con `-A` añade exactamente 30 bytes, los mismos que traen los ficheros
del bucket. O sea, la predicción de arriba se confirma en las dos direcciones: sin `-A` el
pipeline revienta, con `-A` funciona sin tocar nada.

Eso convierte esto en una decisión de producto en vez de en un problema técnico. El campo de
oficina de origen del encabezado sale de la tabla de sitios del CODE —`KMFL` para AMX—, así que
con `-A` los productos del demo llevan el enrutado de una oficina real del Servicio
Meteorológico Nacional de EEUU. Funciona, es la opción que el programa ofrece, y choca con la
regla de etiquetado de salida.

### Opciones, en orden de preferencia

1. **Que el pipeline acepte un `site_id` explícito**, usándolo cuando el encabezado no está. Es
   un cambio pequeño y aditivo en los tres puntos de arriba, no toca el contrato de datos, y el
   runner del job siempre sabe de qué sitio es el trabajo: es él quien acaba de ejecutar
   `change_radar`. Entra en la tabla de [Pendientes](../alcance/pendientes.md).
2. **Derivarlo del `src_id` del encabezado del mensaje.** El producto trae `src_id` en la
   cabecera ICD (728 en el ejemplo de AMX) y `change_radar.dat` fija ese identificador por
   sitio (`rpg_id`). Hay que verificar la correspondencia en F0 antes de fiarse.
3. **Arrancar `nbtcp` con `-A`.** Es la opción soportada y resuelve el problema entero sin
   tocar una línea de código en ningún repo. A cambio, cada producto del demo sale con el
   enrutado de la oficina real del NWS que le corresponde al radar, que es justo lo que la
   regla de etiquetado de [Pendientes](../alcance/pendientes.md) no quiere. Sirve de palanca
   para desatascar F0 —donde nadie de fuera ve nada— y es una conversación aparte para F4.

   Fabricar nosotros el encabezado en el runner tiene el mismo problema y además sin el
   respaldo de la herramienta. No se contempla.

La decisión no se toma aquí: F0 tiene que mirar primero qué escribe `nbtcp` de verdad. Lo que
esta página fija es que **si escribe el producto pelado, el pipeline no lo traga hoy**, y que
eso se sabe antes de montar el contenedor, no después.

## La altura del radar viene en pies y se guarda como metros

!!! danger "Verificado el 2026-11-02. Es un fallo del pipeline, no del demo, pero lo heredamos"
    El bloque de descripción del producto trae la altura del radar **en pies sobre el nivel
    del mar**. `Level3File.height` de MetPy devuelve ese entero tal cual, sin convertir, y el
    pipeline lo asigna a `height_m` y lo escribe en `radars.height_m`.

Dos productos reales del feed, contra el catálogo de sitios de `lamula-process`:

| Sitio | `height` del producto | En metros (×0,3048) | `altM` del catálogo (cota del terreno) |
|---|---|---|---|
| AMX (Miami) | 111 | 33,8 | 4,27 |
| ABX (Albuquerque) | 5951 | 1813,9 | 1789,18 |

La conversión cuadra con la cota del terreno más la torre en los dos casos, con tres órdenes de
magnitud de diferencia entre ellos. No hay otra lectura posible: el número es en pies.

Dónde duele: `ingest/mosaic/service.py:388` pasa ese valor como `antenna_h_m` y
`ingest/mosaic/quality.py:47` lo suma en metros a la altura del haz, que después se pondera con
una altura de referencia de 4000 m. Para un radar costero el error son 178 m (declara 256, que son 78 m) y no se nota. Para
ABX son **4,1 km de más**, que a esa referencia le hunde el peso en todo su dominio. El mosaico
multi-radar de montaña está pesando mal.

Para este repo la consecuencia es más pequeña pero hay que tenerla en cuenta en dos sitios:
`change_radar.dat` quiere la elevación de antena **en pies** (`116` en el ejemplo de kmlb),
mientras que el catálogo de sitios la tiene en metros y además es **cota del terreno, no altura
de antena**. Al generar la línea de un sitio nuevo hay que convertir y sumar la torre, o el
producto saldrá con una altura que no es la del radar del cliente.

## Lo que F0 confirma de este contrato

- [x] ¿Escribe `nbtcp` el encabezado WMO, o el producto pelado? **Respondido en el fuente**:
      pelado salvo que se le pase `-A`.
- [ ] ¿Coincide `src_id` del producto con el `rpg_id` de `change_radar.dat`?
- [ ] ¿Sale `lat`/`lon` del producto con lo que puso `change_radar`? (regla de verificación de
      coordenadas de `AGENTS.md`)
- [ ] ¿Decodifica `l3proc process` los diez productos de la RPS list sin tocar nada más?
