# Hechos verificados del ORPG

Extraído del CODE Guide (B24.0r1.20, octubre 2025) y del trazo de instalación de
`radar-orpg-dev`. Está aquí para que nadie tenga que releer 197 páginas de PDF.

## `play_a2` — entrada de base data

Lee Level II de disco y lo escribe a `$ORPGDIR/ingest/resp.0`, el buffer estándar de entrada
del ORPG. Acepta `.bz2`, `.gz`, `.ar2v` y `.raw`.

| Opción | Efecto |
|---|---|
| `-p playlist` | Lista explícita de ficheros, en orden. No exige convención de nombres. |
| `-d DIR` | Directorio; **recorre subdirectorios** salvo que se use `-r` o `-s`. |
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

Sin `-p`, los ficheros se secuencian por el timestamp del nombre; ficheros de varios radares
que se solapen en el tiempo se entrelazan. Una razón más para usar playlist.

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
la RPS list personalizada, pide la convención de nombres (1–6) y se queda en un menú de nueve
opciones. La RPS list personalizada se deriva del master quitando la cabecera, sin comentarios
ni líneas en blanco, con la primera columna correlativa y la alineación intacta.

`mon_nb 1` monitoriza el enlace; los errores van a `nbtcp.log.<puerto>` en el directorio de
trabajo.

## Ciclo de vida del ORPG

- `mrpg -p -v startup`: arranca y **limpia todos los data stores**. Unos 10 s hasta
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
de granizo. Por esta vía sí existirían. El parser habría que escribirlo.
