# F0 — espiga manual

Instrumental de la Fase 0. **Nada de esto es código del servicio**: son herramientas para medir
el catálogo, preparar los ficheros de la espiga y dejar evidencia reproducible de lo que se va
comprobando. El runner, la cola y la API no se escriben hasta que F0 pase (ver `AGENTS.md`).

Todo corre con `uv run`, sin instalar nada: los scripts llevan sus dependencias declaradas en
la cabecera PEP 723.

## Herramientas

| Script | Para qué |
|---|---|
| `catalogo.py` | Listar, medir y descargar del bucket `unidata-nexrad-level2` |
| `equivalencia.py` | Huella de un producto con el decodificador del pipeline, y comparación de dos huellas |
| `comprobar.py` | Repite contra el bucket real todas las comprobaciones que esta fase da por sabidas |
| `wmo_probe.py` | Evidencia del fallo de `siteID` sin encabezado WMO |
| `integridad.py` | Detecta productos truncados: longitud declarada en la cabecera Level III contra tamaño real |
| `coordenadas.py` | Comprueba que cada producto trae el `siteID` y el `lat`/`lon` esperados (regla de verificación de coordenadas) |

### `catalogo.py`

```bash
# volúmenes de un sitio en un día UTC
f0/catalogo.py list KAMX 2017-09-10

# cadencia, huecos y VCP de una ventana (una petición Range de 64 KiB por volumen)
f0/catalogo.py scan KHGX 2017-08-26T00:00 2017-08-26T06:00 --vcp --gaps

# los cinco casos preparados, medidos
f0/catalogo.py cases --vcp

# parejas Level II / Level III del mismo barrido, para la puerta de equivalencia
f0/catalogo.py pairs KAMX 2026-11-01 --product N0B

# qué formato ofrece un sitio año por año
f0/catalogo.py eras KEVX --desde 2010 --hasta 2016

# descargar doce volúmenes y escribir la playlist que come play_a2
f0/catalogo.py fetch KAMX 2017-09-10T12:00 2017-09-10T18:00 ./vols --max 12
```

Los resultados ya tomados están en
[Catálogo verificado](../docs/referencia/catalogo-verificado.md).

### `equivalencia.py`

La puerta cuantitativa de F0: el mismo barrido por las dos vías tiene que decir lo mismo. El
script saca una huella de cada producto **con el decodificador del pipeline**, no con una
reimplementación, y compara dos huellas campo a campo —identificador, VCP, hora de volumen,
geometría, calibración, fracción de celdas válidas y percentiles del valor físico—.

```bash
# lado de referencia: los diez productos del feed público para un volumen concreto
f0/equivalencia.py referencia KAMX 2026-11-01T00:13:20 --dir ref
f0/equivalencia.py huella ref --salida ref.json

# lado del job: lo que haya escrito nbtcp
f0/equivalencia.py huella salida_nbtcp --salida job.json

f0/equivalencia.py comparar ref.json job.json
```

Comprobado el 2026-11-02 con datos reales: los diez productos del feed decodifican sin tocar
nada, una huella contra sí misma no da ninguna diferencia, y dos volúmenes separados cuatro
minutos dan diferencias en todos los productos. O sea, la herramienta ni falla ni perdona de
más. Lo que falta es el otro lado, que necesita el contenedor.

Devuelve código 1 si hay diferencias, así que sirve de puerta en un script.

### `comprobar.py`

Cada afirmación de las páginas de referencia tiene aquí una comprobación que la repite contra
el bucket real: el 403 de `noaa-nexrad-level2`, los sufijos por era, el VCP leído con una
petición Range, el fallo de `siteID` sin encabezado WMO, la altura en pies de ABX, la
profundidad del archivo de Level III y las parejas Level II/Level III.

```bash
f0/comprobar.py            # las ocho, alrededor de un minuto
f0/comprobar.py wmo altura # solo esas
```

Devuelve 1 si alguna falla. Conviene pasarlo antes de fiarse de un número de hace semanas: el
bucket y MetPy cambian por su cuenta.

## Lo que ya está respondido sin contenedor

- El archivo de `unidata-nexrad-level2` llega hasta **1991**, pero lo seleccionable empieza
  entre **2012 y 2014 según el radar**: antes está en formatos que D9 excluye. Hasta 2015 el
  V06 viene envuelto en gzip (`_V06.gz`), y hay V07 suelto en 2013.
- Las cinco ventanas de huracán medidas: número de volúmenes, bytes, cadencia y VCP.
- **Harvey cambia de VCP a mitad de ventana** (121 → 212).
- Irma trae volúmenes parciales y un corte de 10 minutos.
- Para la puerta de equivalencia sirve cualquier volumen reciente: 302 de 302 volúmenes de KAMX
  del 2026-11-01 tienen su N0B con el mismo sello de tiempo.
- Un producto Level III **sin encabezado WMO** rompe el pipeline en `siteID`
  ([contrato](../docs/referencia/contrato-pipeline.md)).
- Los diez productos del feed decodifican con el pipeline tal cual: siete rásters, dos de
  fenómenos y el perfil de viento. Es el lado de referencia de la comparación, ya listo.
- Un volumen de huracán produce **4,41 MB de COGs** y cuesta 5,6 s de CPU de pipeline; un job
  de doce volúmenes, unos 53 MB y 70 s. El cuello de botella es el ORPG, no `l3proc`
  ([Límites y recursos](../docs/operacion/limites-recursos.md)).
- Las ventanas de los cinco casos preparados, elegidas midiendo el eco y no la hora de
  recalada. Harvey estaba en el día equivocado.

Y leyendo el fuente del CODE (`src/cpc102/tsk060/` y `tsk066/`), tres respuestas más que
estaban anotadas como incógnitas de F0:

- `nbtcp` **no** escribe el encabezado WMO salvo con `-A`, y `-A` además suprime la pregunta de
  la convención de nombres. Con `-b` se va a segundo plano y deja de leer el terminal. La única
  entrada que queda se lee con `scanf`.
- La RPS list se lee con anchos fijos y una línea corta se trata como fin de fichero, sin
  error.
- `play_a2` no descarta radiales por ir rápido, `-T` significa "simula también el hueco entre
  volúmenes" y existe `-m`, máxima velocidad con control de flujo del RPG.

Todo eso dice qué *debería* pasar. Lo que pasa lo dice F0.

## Lo que falta y necesita el contenedor

Esta parte no se ha ejecutado: la sesión que preparó lo de arriba no tenía acceso al demonio de
Docker. **Los comandos literales, en orden, con sus puertas y dónde anotar cada resultado, están
en [F0 en una máquina con Docker](../docs/implementacion/f0-ejecucion.md).** El resumen:

1. **Levantar el ORPG.** `ghcr.io/vladimir1284/orpg:b24`, con `--hostname` fijo (el contenedor
   escribe `$(hostname)` en `.rssd.conf` en cada arranque).
2. **`change_radar -r kamx -S -R` y `mrpg -p -v startup`.** Comprobar en el producto que
   `lat`/`lon` salen los del sitio pedido y no los del anterior: `f0/wmo_probe.py` imprime
   `lat`/`lon` de cualquier producto, y ese es el chequeo.
3. **`nbtcp -A -b` sin terminal interactiva**, con el nombre de la RPS list por stdin. El
   fuente dice que basta; falta verlo. Si no, el plan B es leer el product LB del ORPG.
4. **RPS list recortada a los diez productos** que el pipeline sabe leer: 153, 154, 135, 134,
   170, 173, 172, 58, 141, 48 (ver [contrato](../docs/referencia/contrato-pipeline.md)). Se
   deriva del `master_rps_list.dat` que `nbtcp` regenera al arrancar.
5. **`play_a2 -p playlist`** con la playlist que escribe `catalogo.py fetch`, y después los
   tres modos de velocidad (`-T`, sin `-T`, `-m`) comparados con `equivalencia.py`.
6. **`l3proc process`** sobre lo que escriba `nbtcp`. Aquí se ve si el encabezado WMO está o no.
7. **Encadenar dos sitios distintos** con `mrpg -p startup` en medio y comprobar que no se cuela
   ningún producto del primero.
8. **Medir** lo que pide
   [Límites y recursos](../docs/operacion/limites-recursos.md): RAM pico, CPU media y pico,
   retraso del `processor` live, duración real de doce volúmenes, bytes de productos y COGs.

Un apunte de presupuesto antes de empezar: doce volúmenes de huracán son unos 240 MB de
descarga y, a `-T`, algo más de una hora de reloj.
