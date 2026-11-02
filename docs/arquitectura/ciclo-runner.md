# Ciclo del runner

Un job, de principio a fin. Cada paso dice qué puede salir mal y cómo se corta.

!!! warning "Nada de esto está verificado todavía"
    Los pasos 5 y 6 son la apuesta del diseño. La Fase 0 existe para confirmarlos antes de
    escribir el servicio.

## 1. Tomar el job

`SELECT ... FOR UPDATE SKIP LOCKED` sobre la cola, con `claimed_by` y `claimed_at`. Un runner
que muere deja el job reclamado; un barrido lo devuelve a la cola pasado un timeout, con
contador de intentos. Dos intentos fallidos marcan el job como `failed`, no se reintenta
eternamente.

## 2. Preparar las entradas

Descarga las claves del staging a `/data/ar2in/<job>/`. Si el staging está vacío (primer
intento), las baja de la fuente y las deja en staging primero: un reintento no vuelve a pegarle
a AWS.

Validación antes de gastar una hora de CPU:

- Cabecera `AR2V00xx` en los primeros 9 bytes.
- ICAO idéntico en todos los ficheros (bytes 20–24 de la cabecera de volumen). Comprobada la
  posición el 2026-11-02: la cabecera son 9 bytes de versión, 3 de número de volumen, 4 de
  fecha, 4 de hora y 4 de ICAO.
- Orden cronológico estricto y huecos por debajo del umbral.
- Número de volúmenes dentro de la cuota del token.

!!! warning "Los volúmenes anteriores a 2016 vienen en gzip"
    Las claves que acaban en `_V06.gz` —todo el archivo entre 2013 y 2015— llevan la cabecera
    `AR2V00xx` **dentro** del gzip, así que los dos primeros chequeos hay que hacerlos sobre el
    flujo descomprimido. `play_a2` acepta el `.gz` tal cual, de modo que no hay que
    desempaquetar nada para reproducir; solo para validar. Ver
    [Catálogo verificado](../referencia/catalogo-verificado.md).

## 3. Adaptar el sitio

```
change_radar -r <icao> -S -R
```

`-S` evita que pare el RPG, `-R` que lo arranque. Reescribe `site_info.dea` con lat/lon/elev y
`rpg_id` del sitio; de ahí salen las coordenadas que acaban en la cabecera del producto y, por
tanto, la georreferenciación del COG.

Si el ICAO no está en `~/tools/cfg/change_radar.dat`, el runner **añade la línea** con el
formato `kmlb,28113,-80654,116,302,MELBOURNE` (latitud y longitud en milésimas de grado,
elevación en pies MSL). Para sitios no-WSR-88D los datos vienen del catálogo de sitios; es el
camino que servirá al radar propio del cliente.

!!! danger "Si este paso se salta"
    Los productos salen con las coordenadas del sitio anterior y el COG queda en el lugar
    equivocado del mapa, sin ningún error visible. Verificación obligatoria: el `site_id` y el
    lat/lon que el pipeline inserta en `radars` deben coincidir con los del job.

## 4. Arrancar el ORPG limpio

```
mrpg -p -v startup
```

El `-p` borra los data stores — es lo que hace que un runner persistente sea equivalente a un
contenedor nuevo (D3), y lo que hace efectivo el `change_radar` del paso anterior. Espera a
leer `RPG State: OPERATE` y `RPG Operability Status: ONLINE`; unos 10 s según el trazo de
`radar-orpg-dev`.

Doble cinturón contra fugas entre jobs: directorio de productos por job, y descarte de todo
producto cuyo `vol_time` caiga fuera de la ventana del job.

## 5. Abrir la salida de productos

```
echo rps_lamula.list | nbtcp -A -b -D /data/products/<job> -s <ICAO> -p 4491 -w <passwd> <host>
```

`nbtcp` simula un usuario Class 1 y escribe los productos crudos a ese directorio. Requiere
configuración horneada en la imagen: línea LN=1 con `cm_tcp` en `comms_link.conf`, el enlace
renumerado en `tcp.conf`, y `service_class_table` si se piden más de 160 productos.

Es interactivo, pero menos de lo que parecía. Leído el fuente el 2026-11-02 (detalle en
[Hechos verificados del ORPG](../referencia/orpg-hechos.md)):

- `-A` añade el encabezado WMO —que el pipeline necesita— y además **suprime la pregunta de la
  convención de nombres**.
- `-b` lo manda a segundo plano después de conectar, y deja de leer el terminal.
- La única entrada que queda es el nombre de la RPS list, leída con `scanf`. Un `echo` basta.
- `-D` vacía el directorio al arrancar, que es el cinturón de aislamiento entre jobs.

Queda ejecutarlo: el fuente dice qué debería pasar, F0 dice qué pasa. Plan B si no: leer el
product LB del ORPG directamente.

La RPS list se genera una vez a partir de `master_rps_list.dat` y se hornea en la imagen. Debe
pedir exactamente los productos que el pipeline sabe decodificar: 153 N0B, 154 N0G, 135 EET,
134 DVL, 170 DAA, 173 DU3, 172 DTA, 141 NMD, 58 NST, 48 NVW. El fichero no admite comentarios
ni líneas en blanco, la primera columna es el número de petición y debe ir correlativo, y la
alineación de columnas se respeta.

## 6. Arrancar el procesador

`l3proc watch /data/products/<job>` con el entorno del job:

```
PG_DB=lamula_demo  PG_USER=job_<ulid>  R2_BUCKET=lamula-demo-raster
```

El watcher no discrimina por nombre de fichero, decodifica por contenido, así que la
convención de nombres de `nbtcp` da igual.

Dos opciones de `l3proc watch` que vienen a medida y conviene usar (verificadas contra el CLI
el 2026-11-02): `--heartbeat <fichero>`, que da la señal de vida para detectar un job colgado,
y `--once`, que procesa el backlog y sale. El `--once` es lo que cierra el paso 8 sin
heurística. Las credenciales admiten además la forma `PG_PASSWORD_FILE`, que es como se leen
los secretos del Swarm.

## 7. Reproducir

```
play_a2 -T -p /data/ar2in/<job>/playlist
```

Con playlist, porque los nombres de AWS no siguen la convención de prefijo y timestamp que
espera el modo de línea de comandos. **Sin `-R`**: así el producto lleva el `vol_time`
original (el huracán de 2017 aparece en 2017) y solo la hora de generación es la actual.

`-T` reproduce al ritmo real, unos 5 min por volumen. `-x` queda como perilla, no como
requisito (D6).

Ruido esperado y benigno en la salida: `Bad data: Message type 0`.

## 8. Esperar el final

El job termina cuando `play_a2` sale **y** una pasada final de `l3proc watch --once` sobre el
directorio no deja nada por procesar. Mejor que esperar N segundos sin productos nuevos: lo de
antes era una heurística, esto es una comprobación.

Sigue haciendo falta el timeout duro proporcional al número de volúmenes, y el fichero de
`--heartbeat` del watcher para distinguir "va lento" de "está colgado". Lo que no puede pasar
es que un ORPG colgado deje el runner ocupado para siempre.

## 9. Cerrar

`mrpg shutdown`, esperar a que las tareas operativas salgan (unos 7 s en amd64), borrar los
directorios del job, subir el log a R2, marcar el job `ready` con su ventana de `vol_time`.

Y una fila más, en el schema del job:

```sql
UPDATE radars SET last_seen_at = '<vol_time del último volumen>';
```

Sin eso, el selector de días del viewer sale vacío en cualquier job histórico: ancla su ventana
de 72 horas a `radars.last_seen_at`, y el pipeline escribe ahí la hora de publicación. El
porqué, con el fichero y la línea, en [Componentes](componentes.md).

## Calentamiento: lo que el cliente debe saber

Los algoritmos del ORPG tienen memoria entre volúmenes:

- **SCIT** (NST, NMD) necesita al menos dos volúmenes para trazar movimiento. En el primero no
  hay vectores ni pronóstico.
- **VAD** (NVW) necesita un perfil completo.
- **Acumulados** (DAA, DU3, DTA) construyen lámina de agua a lo largo de horas. Con diez
  volúmenes se ve el principio de una curva, no un acumulado representativo.

Consecuencia de producto: pedir un mínimo de doce volúmenes y marcar los dos primeros como
calentamiento en la interfaz. Decirlo antes evita que el prospecto concluya que el acumulado
está roto.
