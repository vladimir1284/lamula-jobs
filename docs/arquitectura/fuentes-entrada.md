# Fuentes de entrada

El runner solo conoce "claves en staging" (D1). Las fuentes viven en `jobs-api`.

## Fuente 1 — Catálogo público de AWS

Lo verificado en `lamula-process/src/lib/aws-explorer/`, que se reaprovecha:

- Bucket **`unidata-nexrad-level2`**. No `noaa-nexrad-level2`: ese devuelve 403 al listar
  —y también al pedir una clave concreta, revisado el 2026-11-02.
- El archivo llega hasta **1991**, comprobado el 2026-11-02. Los casos de huracán no necesitan
  ninguna fuente aparte.
- Distribución de claves: `YYYY/MM/DD/SITE/SITE_YYYYMMDD_HHMMSS_V0x`, una carpeta por día UTC.
- El sufijo `_V06` filtra lo que el ORPG B24 puede digerir (D9).
- `src/lib/platform/known-sites.json` trae lat/lon/altM de los sitios US, ocho del IDEAM
  colombiano y nueve del INSMET cubano. Sirve de catálogo del selector y de fuente para las
  líneas de `change_radar.dat`.

Se **porta**, no se comparte: aquello es Svelte y el viewer es Vue, y hoy no hay paquete común.
Son unas doscientas líneas entre el listado paginado, la regex de timestamp y el catálogo.

### Interfaz del cliente

Mapa de sitios, día UTC, lista de volúmenes, selección de un rango consecutivo, duración
estimada antes de confirmar.

Encima de eso, un menú de **casos preparados** —Irma/KAMX, Harvey/KHGX, Michael/KEVX,
Ian/KTBW, Milton/KTBW— que rellena sitio y rango de un clic. Los cinco están medidos en
[Catálogo verificado](../referencia/catalogo-verificado.md), y de ahí salen las ventanas
concretas: hora y media cada una, entre 13 y 17 volúmenes, 80-88 minutos de nodo. **La ventana
no es la hora de la recalada**, es la del máximo de eco cerca del radar, que se midió y resultó
ser otra; en el caso de Harvey resultó ser otro día.
Dos cosas que salieron de esa medida y afectan al selector: **Harvey cambia de VCP a mitad de
ventana**, e **Irma trae volúmenes parciales y un corte de diez minutos** —KAMX tenía el
huracán encima—.

Para un demo comercial el menú vale más que el selector libre: el prospecto ve una tormenta
reconocible en vez de tener que adivinar una fecha con eco.

## Fuente 2 — Observaciones propias del cliente (futura)

La herramienta que convierte las observaciones del cliente a Level II (terreno de
`lamula-rcp`, que ya archiva Level II y emula un RDA). Cuando exista, el flujo es: la
herramienta deja los volúmenes en staging y `jobs-api` crea el job con esas claves. El runner
no se entera de la diferencia.

Lo que esa fuente añadirá, y conviene tener previsto:

- Validación más dura: aquí los ficheros no vienen de un bucket confiable.
- Sitios no-WSR-88D: línea nueva en `change_radar.dat` con los datos del cliente.
- Cuotas por tamaño, no solo por número de volúmenes.
