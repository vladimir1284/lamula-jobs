# Catálogo verificado

Medidas reales del bucket `unidata-nexrad-level2`, tomadas el **2026-11-02** con
`f0/catalogo.py`. Están aquí para que el selector, las cuotas y la estimación de duración se
diseñen con números y no con supuestos.

## Lo que hay en el bucket

| Comprobación | Resultado |
|---|---|
| Profundidad del archivo | Prefijos de año **1991 a 2026**, sin huecos (más uno espurio, `1970/`) |
| Profundidad **seleccionable** (V06) | Depende del sitio: entre 2012 y 2014. Ver más abajo |
| Caso más antiguo que vendemos (Irma, 2017) | Presente y completo |
| `noaa-nexrad-level2` como alternativa | **403** anónimo tanto al listar como al hacer `GET` de una clave real |
| Nombre de clave | `YYYY/MM/DD/SITE/SITE_YYYYMMDD_HHMMSS_V0x`, con `.gz` hasta 2015 |

El menú de casos preparados de [Fuentes de entrada](../arquitectura/fuentes-entrada.md) no
depende de ninguna fuente nueva: un huracán de 2017 se sirve del mismo sitio que el volumen de
esta mañana. Lo que sí hay que decirle al selector es desde cuándo.

## Eras de formato

D9 solo admite V06 (Message 31). El archivo guarda cada año con el formato de su época, y el
cambio **no es una fecha global, es por radar**:

| Sitio | …2011 | 2012 | 2013 | 2014 | 2015 | 2016… |
|---|---|---|---|---|---|---|
| KAMX | V03.gz | **V06.gz** | V06.gz | V06.gz | V06.gz | V06 |
| KHGX | V03.gz | V03.gz | **V06.gz** | V06.gz | V06.gz | V06 |
| KTBW | V03.gz | **V06.gz** | V06.gz | V06.gz | V06.gz | V06 |
| KEVX | V04.gz | V04.gz | **V07.gz** | V06.gz | V06.gz | V06 |

(muestreo del 15 de junio de cada año, `f0/catalogo.py eras`)

Tres consecuencias para el selector, las tres pequeñas y las tres capaces de costar una tarde:

1. **Hasta 2015 el V06 viene envuelto en gzip**, con la clave terminada en `_V06.gz`. Un filtro
   por `endswith("_V06")` los descarta en silencio. `play_a2` acepta `.gz` directamente, así que
   no hay que desempaquetar nada: solo contarlos.
2. **Existe V07 en el archivo.** KEVX, 2013, cabecera `AR2V0007.706`. D9 nombraba V03, V04 y
   V05 como lo excluido; V07 no estaba en la lista. El filtro tiene que ser **lista blanca**
   (`_V06`, `_V06.gz`) y no lista negra. Si algún día interesa 2013 en KEVX, antes hay que
   averiguar si el ORPG B24 traga AR2V0007.
3. **Hay ficheros `_V06_MDM`**, unas 24 al día. No son volúmenes y el listado los salta.

El límite inferior útil del catálogo es, en la práctica, **2012-2014 según el radar**. Para el
selector eso significa consultar el formato antes de ofrecer un año, no suponerlo.

## Los casos preparados, medidos

Ventana de seis horas centrada en el paso por el radar:

| Caso | Sitio | Ventana UTC | Vols V06 | Tamaño | MB/vol | Cadencia mediana | VCP |
|---|---|---|---|---|---|---|---|
| Irma | KAMX | 2017-09-10 12:00–18:00 | 57 | 1124 MB | 19,7 | 391 s | 212 |
| Harvey | KHGX | 2017-08-26 00:00–06:00 | 66 | 774 MB | 11,7 | 329 s | **121 → 212** |
| Michael | KEVX | 2018-10-10 14:00–20:00 | 69 | 1033 MB | 15,0 | 305 s | 212 |
| Ian | KTBW | 2022-09-28 15:00–21:00 | 54 | 1035 MB | 19,2 | 400 s | 112 |
| Milton | KTBW | 2024-10-09 20:00–02:00 | 53 | 1165 MB | 22,0 | 400 s | 212 |

Reproducir cualquiera de estas ventanas entera con `play_a2 -T` cuesta **unas seis horas de
nodo**, porque `-T` respeta el intervalo real. La ventana que se le ofrece al cliente la fija el
reloj, no el catálogo: 12 volúmenes son una hora larga de ejecución.

### Consecuencias directas

1. **El tamaño por volumen depende del tiempo que hacía.** Un volumen de huracán ocupa de 12 a
   25 MB; uno de día tranquilo (KAMX, 2026-10-30) ocupa 5,9 MB. Son cuatro veces. Una cuota
   expresada solo en número de volúmenes deja que un job de nivel `demo` mueva entre 70 MB y
   300 MB de staging, y uno de `evaluacion` hasta 1,2 GB. Conviene que
   [Acceso y cuotas](../operacion/acceso-y-cuotas.md) lleve también un tope en bytes.
2. **El cambio de VCP a mitad de ventana no es hipotético.** Harvey lo tiene dentro: KHGX pasa
   de VCP 121 a VCP 212 a las 01:50:52 UTC, hora y media después del comienzo de la ventana. Es
   uno de los cinco casos que queremos enseñar.
3. **Los casos buenos traen volúmenes rotos.** Ver abajo.

## Volúmenes parciales y huecos

En la ventana de Irma, KAMX —que estaba recibiendo el huracán encima— produce:

| Hora UTC | Hueco respecto al anterior | Tamaño | Tamaño típico ese día |
|---|---|---|---|
| 14:50:22 | 79 s | 21,2 MB | ~24,6 MB |
| 14:57:57 | 47 s | 19,1 MB | ~24,6 MB |
| 15:32:21 | 109 s | 15,3 MB | ~24,6 MB |
| 16:34:10 | 104 s | 9,7 MB | ~24,6 MB |

Y un hueco de **10 minutos exactos** entre 16:22:25 y 16:32:26.

Lectura: el archivo contiene volúmenes abortados —el RDA se reinició varias veces con la
tormenta encima— y un corte de servicio. No son datos corruptos, son observaciones reales de
un radar en apuros, y están justo en el caso que mejor vende. El runner tiene que tragarlos sin
caerse, y la línea de tiempo del viewer tiene que poder enseñar un hueco.

Con `-T`, un hueco de diez minutos son diez minutos de nodo sin hacer nada. De ahí la propuesta
de umbral de [Pendientes](../alcance/pendientes.md).

## El tamaño del fichero no mide la tormenta

Parecía un atajo: un volumen comprime peor cuanto más eco tiene, así que los bytes que ya
devuelve el listado deberían servir de proxy de intensidad y ahorrar descargas. **No sirve.**

KTBW el día de Ian, 206 volúmenes, uno de cada cuatro perfilado:

| Patrón | Horas | MB mínimo | MB mediana | MB máximo |
|---|---|---|---|---|
| VCP 212 | 00:03–12:40 | 19,8 | 23,4 | 25,0 |
| VCP 112 | 13:09–23:49 | 16,2 | 18,8 | 21,0 |

La recalada fue por la tarde, dentro del tramo de VCP 112 —el de los ficheros **pequeños**—. Lo
que domina el tamaño es el patrón de barrido: cuántos cortes de elevación y a qué resolución,
no cuánta lluvia hay delante. Elegir ventana por bytes elige el patrón más caro, no la tormenta
más fuerte.

`f0/catalogo.py ventana` sigue existiendo y sigue eligiendo por bytes, pero para lo que sí vale:
dimensionar el peor caso de descarga y de staging.

## Los dos archivos no tienen la misma profundidad

| Bucket | Primer dato |
|---|---|
| `unidata-nexrad-level2` (base data) | 1991, utilizable desde 2012-2014 según el radar |
| `unidata-nexrad-level3` (productos) | **entre el 1 y el 5 de marzo de 2022** |

Consecuencia directa, y no es menor: para un caso anterior a marzo de 2022 **no existe producto
oficial con el que comparar**. La puerta de equivalencia de F0 solo se puede ejecutar con datos
recientes; Irma, Harvey y Michael no tienen lado de referencia. Y si alguna vez se quiere
enseñar en el viewer "lo nuestro contra lo oficial" en un caso preparado, solo Ian y Milton lo
permiten.

Visto de otro modo: lo que el demo genera para un huracán de 2017 **no existe en ningún
archivo público**. Es un argumento de venta, no un problema.

## Equivalencia Level II ↔ Level III

La puerta de equivalencia de F0 necesita el mismo barrido por las dos vías. Comprobado para
KAMX el 2026-11-01:

- **302 de 302** volúmenes V06 del día tienen su N0B en `unidata-nexrad-level3` con el **mismo
  sello de tiempo al segundo**.
- La correspondencia de nombres es directa:
  `2026/11/01/KAMX/KAMX20261101_000043_V06` ↔ `AMX_N0B_2026_11_01_00_00_43`.

O sea: para la validación cuantitativa no hay que buscar una pareja afortunada, sirve cualquier
volumen de un día reciente. `f0/catalogo.py pairs` las lista.

## Cómo se tomaron estas medidas

`f0/catalogo.py` lista con `ListObjectsV2` anónimo y lee el VCP sin bajarse el volumen. Una
petición `Range` de 64 KiB basta en las dos disposiciones que conviven en el archivo:

- **Desde 2016**: cabecera de volumen de 24 bytes y registros LDM comprimidos por separado con
  bzip2. El primero es el de metadatos y ocupa **unos 2,4 KB**; se recorta por su frontera
  exacta y lo decodifica MetPy.
- **Hasta 2015**: el fichero entero envuelto en gzip, con los mensajes sin comprimir por
  dentro. Se descomprime el prefijo que haya llegado —64 KiB de gzip dan unos 750 KB— y se
  recorren los segmentos de 2432 bytes hasta el mensaje 5, que suele caer sobre los 320 KB.

Un día entero de un sitio se perfila con ~2 MB de tráfico en vez de 6 GB.

```bash
f0/catalogo.py cases --vcp
f0/catalogo.py eras KEVX --desde 2010 --hasta 2016
f0/catalogo.py ventana KTBW 2022-09-28T00:00 2022-09-29T00:00 -n 12
f0/catalogo.py scan KAMX 2017-09-10T12:00 2017-09-10T18:00 --vcp --gaps
f0/catalogo.py pairs KAMX 2026-11-01 --product N0B
```
