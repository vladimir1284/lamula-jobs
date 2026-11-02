# Hechos verificados del ORPG

Extraído del CODE Guide (B24.0r1.20, octubre 2025) y del trazo de instalación de
`radar-orpg-dev`. Está aquí para que nadie tenga que releer 197 páginas de PDF.

## `play_a2` — entrada de base data

Lee Level II de disco y lo escribe a `$ORPGDIR/ingest/resp.0`, el buffer estándar de entrada
del ORPG. Acepta `.bz2`, `.gz`, `.ar2v` y `.raw`.

| Opción | Efecto |
|---|---|
| `-p playlist` | Lista explícita de ficheros, en orden. **Solo para bz2 de volumen entero**: no reconoce el formato LDM del bucket de Unidata (ver abajo). |
| `-d DIR` | Directorio; **recorre subdirectorios** salvo que se use `-r` o `-s`. Es el único modo que acepta los volúmenes de `unidata-nexrad-level2`. |
| `-s fichero` | Empezar por ese fichero. |
| `-r PREFIJO` | Solo ficheros con ese prefijo. |
| `-n N` | Solo N volúmenes. |
| `-T` | Respeta el intervalo real entre volúmenes. |
| `-x factor` | Multiplicador de velocidad. `2` es el doble, `0.5` la mitad. |
| `-R` | Fuerza el `vol_time` a la hora actual. |
| `-c` | Bucle continuo. |
| `-t` | Simulacro: dice qué reproduciría, sin ingerir. |

Con datos históricos y **sin `-R`**, el `vol_time` del producto es el de la observación y la
hora de generación es la actual. Es lo que queremos.

### Cómo pacea de verdad, leído del fuente (2026-11-02)

`src/cpc102/tsk066/pa_playback.c`, función `Speed_control`, llamada una vez por mensaje de
radial:

- El tiempo que espera sale de comparar el tiempo de los datos con el del reloj, dividido por
  la velocidad de `-x`. Nada en `play_a2` descarta radiales por ir rápido: `-x` solo escala
  esa cuenta. Si se pierden datos, se pierden aguas abajo, en la ingesta del RPG.
- **Cada espera está topada en 200 ms**, con un comentario en el código que dice que sin ese
  tope se perdían cortes de un volumen concreto de 2017. O sea, un hueco de diez minutos no se
  espera de una sentada: se reparte en esperas de 200 ms entre los mensajes siguientes.
- **`-T` no significa "a tiempo real"**, significa que el tiempo *entre* volúmenes también se
  simula. Sin `-T`, el reloj de referencia se reancla al empezar cada volumen, así que los
  huecos entre volúmenes —y el tiempo muerto del archivo— sencillamente no se esperan.
- `-m` es otra cosa y merece una prueba: reproduce a la máxima velocidad **con control de
  flujo**, gobernado por un evento del RPG que confirma cortes completados. Es decir, va tan
  rápido como el RPG admite, no tan rápido como pueda el disco.
- `-w ms` fija una espera mínima entre radiales, por si hace falta frenar a mano.

Tres modos distintos, entonces, y solo uno está probado por nosotros (ninguno): `-T` (duración
igual a la ventana real), sin `-T` (se saltan los huecos) y `-m` (lo que el RPG aguante).

Sin `-p`, los ficheros se secuencian por el timestamp del nombre; ficheros de varios radares
que se solapen en el tiempo se entrelazan. Con `-d` hay que dar a cada job **un directorio
propio con solo sus volúmenes**.

Mensajes benignos documentados: `Bad data: Message type 0` (metadato moderno que `play_a2`
ignora) y desfases en la fecha mostrada para volúmenes creados con `save_volume_file`.

## `change_radar` — adaptación de sitio

Reescribe `site_info.dea`: `rpg_name`, `rda_lat`, `rda_lon`, `rda_elev`, `rpg_id`. De ahí salen
las coordenadas de la cabecera del producto, el mapa de fondo y el identificador que ve el
usuario.

- `change_radar -r <icao> -S -R` — `-S` no apaga el RPG, `-R` no lo reinicia.
- **Los cambios no entran hasta un `mrpg -p startup`**, que borra la adaptación binaria previa.
- `change_radar -l` lista los sitios soportados.
- Datos en `~/tools/cfg/change_radar.dat`, una línea por sitio y sin espacios de más:
  `kmlb,28113,-80654,116,302,MELBOURNE` = ICAO, latitud en milésimas de grado, longitud en
  milésimas, elevación de antena en pies MSL, id de sitio, nombre.
- Para radares no-WSR-88D (el caso del cliente con radar propio) se añade la línea a mano. Es
  el camino soportado por la propia documentación.
- Requiere `ORPG_NONOPERATIONAL` definido, cosa que la instalación de CODE ya hace.

## `nbtcp` — salida de productos

Simula un usuario Class 1 (ICD 2620001) y guarda los productos crudos en un directorio.

```
nbtcp -p <puerto> -s <SITIO> -d <directorio> -w <clave> <host>
```

Por defecto puerto 4491 y clave `passwd`.

Configuración previa, horneable en la imagen:

1. `comms_link.conf`: descomentar la línea LN=1, cambiar `cm_tcp_` por `cm_tcp`, subir
   `number_links`. Valores: `LN=1, UN=1, CN=1, DN=1, PN=0, LT=Dedic, LR=100000, CS=cm_tcp,
   MPS=128, NS=2, LS=0, DEN=1, CLASS=98, TOUT=0`.
2. `tcp.conf`: renumerar un enlace libre (el 27 sirve) al 1, servidor, dedicado, con el
   hostname real.
3. `service_class_table`: la clase 98 permite 160 peticiones. Solo hay que tocarlo si la RPS
   list pide más.
4. Los cambios entran con `mrpg -v -p startup`.

**Es interactivo**: al arrancar regenera `master_rps_list.dat` en `CFG_DIR`, pide el nombre de
la RPS list personalizada, pide la convención de nombres (1–7) y se queda en un menú. La RPS
list personalizada se deriva del master quitando la cabecera, sin comentarios ni líneas en
blanco, con la primera columna correlativa y la alineación intacta.

### Cómo se automatiza, leído del fuente (2026-11-02)

Leído en `src/cpc102/tsk060/` del tarball `rpg_b24_0r1_20_pub_src.tgz`. Tres opciones que la
página de ayuda del propio programa lista y que cambian el panorama:

| Opción | Qué hace |
|---|---|
| `-A` | Añade el encabezado WMO/AWIPS a cada producto. **Por defecto no lo añade.** |
| `-C` | País de origen para ese encabezado (por defecto, EEUU). |
| `-b` | Manda `nbtcp` a segundo plano. Solo con TCP e interfaz nativa. |
| `-D` | Como `-d`, pero vacía el directorio al empezar. |
| `-R` | Borra productos de más de X minutos. |
| `-i` | Con `-d`, no guarda productos de código menor que 16. |

Y el detalle que de verdad desatasca: en `nbtcp.c`, la pregunta de la convención de nombres
**solo se hace cuando no se ha pedido el encabezado**. Con `-A`, el programa fija la convención
8 —derivada del propio encabezado— y no pregunta nada.

Queda una sola entrada interactiva: el nombre del fichero de RPS list, que se lee con un
`scanf` de la entrada estándar y **no** se salta con `-n` (esa opción solo evita mandar la
lista al conectar). Un `echo` o un here-string basta.

#### El formato de la RPS list, por qué es quisquilloso

`nbtcp_read_product_list.c` lee cada línea con un `fscanf` de anchos fijos: 4 caracteres de
número de petición, 5 de código de producto, 5 de mnemónico, **51 leídos como caracteres —no
como palabra—** para la descripción, y seis parámetros sueltos. Diez campos por línea.

De ahí salen las tres reglas, y ahora con su motivo:

- La **alineación importa de verdad**: la descripción se lee por posición, no por separador.
- No hay comentarios ni líneas en blanco porque el lector no los contempla.
- Y la trampa: si una línea da menos de diez campos, el lector **marca fin de fichero**. No da
  error, no avisa: deja de leer ahí. Una RPS list mal formada en la línea 7 se convierte en
  una RPS list de seis productos, y el síntoma aparece mucho después, como productos que
  faltan.

Con `-b`, después de conectar el programa deja de leer el terminal, así que no hay menú que
atender.

Receta que resulta de todo esto, para probar en F0:

```bash
echo rps_lamula.list | nbtcp -A -b -D /data/products/<job> -s <ICAO> -p 4491 -w <clave> <host>
```

El encabezado que añade `-A` mide **30 bytes** (`WMO_HEADER_SIZE` en `nbtcp.h`), que es
exactamente lo que miden los del bucket de Unidata, y su campo de oficina de origen sale de la
tabla de sitios del propio CODE: para AMX, `KMFL`. Es decir, con `-A` los productos del demo
salen con el enrutado de la oficina real del NWS. Hay que decidirlo a propósito, no por
defecto: ver [Contrato con el pipeline](contrato-pipeline.md).

`mon_nb 1` monitoriza el enlace; los errores van a `nbtcp.log.<puerto>` en el directorio de
trabajo.

## Ciclo de vida del ORPG

- `mrpg -p -v startup`: arranca y **limpia todos los data stores** (confirmado en
  `src/cpc111/tsk001/mrpg_main.c`: `-p` activa el camino de limpieza completa; si el RPG está
  operativo cuando se pide, antes ejecuta un `rescue_data save`, que cuesta su tiempo). Unos 10 s hasta
  `RPG State: OPERATE` / `RPG Operability Status: ONLINE`. Después, 107 tareas en amd64, 105 en
  arm64.
- `mrpg shutdown` solo **manda** la orden; las tareas operativas tardan unos 7 s en salir.
  `rssd`, `mrpg`, `owr_server` y `nds` siguen vivos por diseño.
- El contenedor de producción pinta `$(hostname)` en el `Client:` de `.rssd.conf` en cada
  arranque, así que conviene fijar `--hostname`.

## Lo que el ORPG genera y el feed público no distribuye

HI (59, granizo), TVS (61) y SS (62, estructura de tormenta). El pipeline los dio por fuera de
alcance porque el bucket de Unidata no los lleva —barrido de junio y julio de 2026, cero
claves—, y por eso `phenomena.attrs` no trae VIL por celda, eco tope por celda ni probabilidad
de granizo. Por esta vía sí existirían.

El parser habría que escribirlo, pero menos de lo que parecía: MetPy 1.7.1 tiene los códigos
59, 61 y 62 en su tabla de productos (comprobado el 2026-11-02), así que los abre y expone sus
bloques. Lo que falta es el mapeo a `phenomena`, comparable a `_parse_nst` y `_parse_nmd`.


## Verificado en F0 (2026-11-02)

Primera ejecución real, en el contenedor `orpg-f0` (imagen `orpg-prod:b24`, KAMX, volúmenes de
Irma del 2017-09-10). Los comandos están en [F0 en una máquina con Docker](../implementacion/f0-ejecucion.md).

| Hecho | Evidencia |
|---|---|
| `nbtcp -A -b -D dir -s KAMX -p 4491 -w passwd orpg-f0` con `echo lista \|` **arranca sin terminal** y vuelve con código 0 | `nbtcp.log.4491`: sockets conectados, login, RPS list enviada con 10 productos |
| El último argumento decide la interfaz: ≤2 caracteres es enlace `cm_tcp`, más es host y usa la nativa | `nbtcp.c:803-830`; con `1` falla buscando `nbtcp/nbtcp_comms_link.conf` |
| Con `-A` no hay pregunta de convención y el originador de KAMX sale `KMFL` | Salida de `nbtcp`: `WMO Originator for Site: KAMX: KMFL`; ficheros `KMFL_SDUS82_…AMX_…` |
| `change_radar -r kamx -S -R` + `mrpg -p -v startup` deja las coordenadas de KAMX | `RDA LATITUDE: 25611`, `RDA LONGITUDE: -80413` |
| Con `-p`, los volúmenes del bucket **no se leen**: `BZ2_bzRead failed (error -5)` | `pa_files.c:565` marca todo fichero de playlist como `AP_NCDC_TYPE`; `-d` los clasifica por nombre y sí funciona |
| `mrpg -p -v startup` termina en ~2 s pero el proceso no sale | `ps` tras `startup completed` |
| `play_a2 -m` no es rápido: **12 volúmenes en 4 670 s** (78 min, ~6,5 min/volumen); con 2 volúmenes fueron 741 s | `f0-run/run_modes.sh`, enlace `LR=100000`; 127 ficheros de salida |
| `nbtcp` cierra los sockets por `AWIPS product completion timer expired` y reconecta tras productos grandes | `nbtcp.log.4491` |
| **Un producto puede quedar truncado sin error**: un N0B declaraba 401 427 B y se guardaron 399 360 | `f0/integridad.py`; el siguiente N0B, completo, decodifica y su flujo bz2 da 1 329 150 B, igual que el de referencia del bucket |

### Paso 6: decodificar con el pipeline (2026-11-02, corrida `-m` en curso)

Copia de 68 ficheros de `products-m` por `l3proc watch --once --no-publish`: 47 procesados, 21
fallidos, y los 21 se explican por dos causas.

| Hecho | Evidencia |
|---|---|
| **El truncado de N0B es la regla, no la excepción**: 8 de 12 N0B de la pasada `-m` completa salieron cortados (los cuatro enteros fueron cuestión de tiempo), siempre en múltiplos de 10 240 B | `f0/integridad.py`; `l3proc` los rechaza con un aviso de MetPy y un `ValueError` (el fallo es ruidoso aguas abajo) |
| La causa es `#define AWIPS_PRODUCT_COMPLETION_TIME 30` en `nbtcp_process_rpg_msgs.c:90`: si el producto no ha llegado entero 30 s después de empezar, `nbtcp` cierra los sockets | El log muestra cada N0B empezando y cerrándose exactamente 30 s después, a ~13 KB/s |
| **Hipótesis sin probar**: el límite es la velocidad del enlace, `LR=100000` (100 kbit/s) del runbook; 400 KB a esa velocidad son ~32 s. Se sube a `LR=1536000` para la pasada `-T` | Aritmética + el ritmo observado; la prueba es que `products-T` salga sin truncados |
| Los `GSM…_210602060628[.n]` (230 B, estado general) **no son productos** y `l3proc` los falla: hay que filtrarlos antes de entregar el job al pipeline | 16 de los 21 fallos |
| `l3proc watch` **consume** su directorio de entrada (mueve a `failed/` lo que falla y borra lo procesado) y guarda estado en `.heartbeat` | Hay que darle una copia, nunca el directorio vivo de `nbtcp` |
| Salen también ficheros `P173_173_E0_KAMX_<fecha>` (232 B), respuesta de estado de la petición 173; tampoco son productos | Directorio de salida de `nbtcp` |

La RPS list personalizada se derivó del maestro tomando la primera línea de cada uno de los diez
códigos (153 y 154 con su primer ángulo de elevación). `master_rps_list.dat` aparece en
`$CFG_DIR` tras ejecutar `nbtcp` una vez.
