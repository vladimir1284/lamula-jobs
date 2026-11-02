# F0 en una máquina con Docker

Esta página existe porque la sesión que preparó toda la Fase 0 **no tenía acceso al demonio de
Docker**: `permission denied while trying to connect to the Docker daemon socket`. Todo lo que
se podía responder leyendo, midiendo el catálogo o leyendo el fuente del CODE está respondido;
lo que falta necesita el contenedor y está aquí, en orden, con los comandos literales.

Léela junto a [Fases](fases.md), que dice cuáles son las puertas, y al `README.md` de `f0/`,
que dice qué hace cada herramienta.

## Lo que hace falta en la máquina

| Qué | Por qué | Comprobación |
|---|---|---|
| Docker con permiso de usuario | Levantar el ORPG | `docker ps` sin `sudo` |
| Login en GHCR | La imagen `ghcr.io/vladimir1284/orpg:b24` es **privada** | `docker login ghcr.io` |
| `uv` | Las herramientas de `f0/` y el pipeline | `uv --version` |
| `nexrad-l3-pipeline` clonado al lado | `equivalencia.py` importa sus decodificadores | `ls ../nexrad-l3-pipeline/ingest` |
| Salida a internet sin credenciales AWS | El bucket de Unidata es anónimo | `f0/comprobar.py noaa` |
| 2 GB de disco y ~240 MB de descarga | Doce volúmenes de huracán | — |
| 2 h de reloj sin tocar nada | A `-T` son 5 min por volumen | — |

Si la imagen no se encuentra con el tag `b24`, se publicó por arquitectura: prueba
`ghcr.io/vladimir1284/orpg:b24-amd64` o `:b24-arm64`. Las dos están validadas de punta a punta
(ver `docs/production-image.md` de `radar-orpg-dev`).

!!! success "Lo que F0 **no** necesita"
    Ni Postgres, ni R2, ni el Swarm, ni credenciales de Cloudflare. `l3proc process` sin
    `--publish` y `l3proc watch --no-publish` escriben los COG en disco y no tocan ningún
    almacén —verificado en `ingest/cli.py`—, y `f0/equivalencia.py` usa los decodificadores del
    pipeline como librería. F0 corre entero en un portátil.

## El hueco que hay que tapar a mano

La imagen `orpg:b24` arranca el ORPG y llega a `OPERATE`/`ONLINE`, pero **no trae la
configuración de `nbtcp`**: eso se horneará en la imagen del runner en F1, cuando F0 diga qué
configuración funciona de verdad. En F0 se hace a mano dentro del contenedor, y lo que se anote
aquí es el insumo de F1.

Son tres ficheros en `$CFG_DIR` (ver [Hechos verificados del
ORPG](../referencia/orpg-hechos.md) para los valores exactos):

1. `comms_link.conf` — línea `LN=1` descomentada, `cm_tcp_` → `cm_tcp`, `number_links` arriba.
2. `tcp.conf` — un enlace libre (el 27) renumerado al 1, servidor, dedicado, con el hostname
   real del contenedor.
3. `service_class_table` — solo si la RPS list pide más de 160 productos. La nuestra pide diez.

Los cambios entran con `mrpg -v -p startup`, que es el mismo arranque del paso 3.

!!! warning "`mrpg -p startup` no sale"
    El arranque termina en unos 2 s (línea `RPG startup completed`) pero el proceso `mrpg` sigue
    vivo. Encadenado a un pipe (`| tail`) la orden no vuelve nunca. Redirige a fichero y espera
    esa línea; no esperes a que el proceso termine.

## Paso a paso

### 1. Preparar las entradas, fuera del contenedor

```bash
cd ~/workspace/lamula-jobs
f0/comprobar.py                     # 8/8 antes de empezar; si falla algo, el bucket cambió
f0/catalogo.py cases --vcp          # recuerda las cinco ventanas medidas
mkdir -p f0-run/ar2in f0-run/products f0-run/cogs
f0/catalogo.py fetch KAMX 2017-09-10T17:00 2017-09-10T18:30 f0-run/ar2in --max 12
```

`fetch` deja los volúmenes y escribe una `playlist`, **que no sirve para estos volúmenes**:
`play_a2 -p` trata todo fichero de la lista como bz2 de volumen entero y falla con
`BZ2_bzRead failed (error -5)`. Los del bucket son formato LDM (cabecera `AR2V` y bloques bz2) y
solo se reconocen con `play_a2 -d <directorio>`, que clasifica por nombre. Medido el 2026-11-02;
ver [Hechos verificados](../referencia/orpg-hechos.md#verificado-en-f0-2026-11-02). KAMX/Irma es el caso de
arranque porque es el más denso; para la primera pasada sirve cualquiera, y para ir rápido
bastan dos volúmenes (`--max 2`).

**Anota:** cuántos volúmenes, cuántos bytes, qué VCP y si hay huecos.

### 2. Levantar el ORPG

```bash
docker login ghcr.io
docker run -d --name orpg-f0 --hostname orpg-f0 --stop-timeout 30 \
  -v "$PWD/f0-run:/data" ghcr.io/vladimir1284/orpg:b24
# sin login en GHCR sirve la imagen local de producción de radar-orpg-dev: orpg-prod:b24
docker logs -f orpg-f0        # termina en "RPG System Startup Completed", ~10 s
```

- `--hostname` fijo: el `entrypoint.sh` escribe `$(hostname)` en el `Client:` de `.rssd.conf` en
  cada arranque, y `tcp.conf` tiene que casar con él.
- `--stop-timeout 30`: `mrpg shutdown` vuelve enseguida pero las tareas operativas tardan unos
  7 s en salir de verdad.
- El bind mount es la única vía por la que los productos salen del contenedor. El usuario
  interno es `orpg`, uid 1000, igual que el usuario del host en la imagen de desarrollo, así que
  los permisos cuadran sin más.

Dentro, siempre con shell de login, que es de donde salen `ORPGDIR`, `ARCH` y `PATH`:

```bash
docker exec -it -u orpg orpg-f0 bash -l
rpg_ps | wc -l        # unas 107 tareas
```

### 3. Cambiar de sitio y rearrancar

```bash
change_radar -r kamx -S -R
mrpg -p -v startup
```

Espera a `RPG State: OPERATE` y `RPG Operability Status: ONLINE`.

**Puerta:** el `lat`/`lon` del primer producto tiene que ser el de KAMX y no el de KMLB, que es
el sitio de ejemplo con el que se configuró la imagen. `f0/wmo_probe.py` imprime `lat`/`lon` de
cualquier producto; ese es el chequeo. Un `change_radar` que no surtió efecto **no da ningún
error**, solo COGs en el sitio equivocado.

### 4. Abrir la salida de productos

Primero la RPS list. `nbtcp` regenera `master_rps_list.dat` en `$CFG_DIR` al arrancar; de ahí
se derivan las diez líneas que el pipeline sabe leer (153, 154, 135, 134, 170, 173, 172, 58,
141, 48). Respeta la alineación de columnas y la numeración correlativa: el lector usa anchos
fijos y **una línea con menos de diez campos se trata como fin de fichero, sin error** —una RPS
list rota en la línea 7 se convierte en una lista de seis productos y el síntoma aparece mucho
después.

```bash
echo rps_lamula.list | nbtcp -A -b -D /data/products -s KAMX -p 4491 -w passwd orpg-f0
# El ÚLTIMO argumento decide la interfaz: de 2 caracteres o menos es un enlace cm_tcp (falla
# buscando nbtcp_comms_link.conf); de más, un host y se usa la interfaz nativa. Es el hostname.
mon_nb 1                              # estado del enlace; interactivo, no lo lances sin timeout
tail -f nbtcp.log.4491                # errores
```

**Puertas de este paso, que son las que pueden matar el diseño:**

1. ¿Arranca sin terminal interactiva? El fuente dice que sí: `-A` fija la convención de nombres
   y suprime esa pregunta, `-b` lo manda a segundo plano, y la única entrada que queda se lee
   con `scanf`. **Falta verlo.** Si no, el plan B es leer el product LB del ORPG directamente, y
   eso se evalúa antes de seguir.
2. ¿Los productos traen los 30 bytes de encabezado WMO? Sin ellos el pipeline muere en `siteID`
   ([Contrato con el pipeline](../referencia/contrato-pipeline.md)). Pruébalo **también sin
   `-A`**, para confirmar el fallo y tener la evidencia de por qué `-A` no es opcional.
3. ¿Qué oficina de origen pone en el encabezado? Para AMX debería ser `KMFL`, la oficina real
   del NWS. Es una decisión de producto pendiente, no un fallo: anótala.

### 5. Reproducir

```bash
play_a2 -T -d /data/ar2in
```

Sin `-R`, para que el producto conserve el `vol_time` original. `Bad data: Message type 0` en la
salida es ruido esperado y benigno.

Después, la medida que reabre D6: los **mismos** volúmenes por los tres caminos, cronometrados.

```bash
play_a2 -T -d /data/ar2in     # ritmo real, simula también el hueco entre volúmenes
play_a2 -d /data/ar2in        # sin el hueco
play_a2 -m -d /data/ar2in     # máxima velocidad, control de flujo del propio RPG
```

Guarda la salida de cada modo en un directorio distinto (`-D` apunta a otro sitio, o copia el
directorio entre pasadas) y compáralos:

```bash
f0/equivalencia.py huella f0-run/products-T  --salida T.json
f0/equivalencia.py huella f0-run/products-m  --salida m.json
f0/equivalencia.py comparar T.json m.json
```

**Si salen iguales, el demo deja de costar hora y media por job**, y eso cambia las cuotas, los
niveles de token y hasta si el servicio tiene que ser asíncrono. Es decir, cambia F2 y F4 antes
de escribirlos. Anota la duración de reloj de cada modo.

### 6. Decodificar

Fuera del contenedor, sin publicar nada:

```bash
cd ~/workspace/nexrad-l3-pipeline
uv run l3proc process ~/workspace/lamula-jobs/f0-run/products/<fichero> -o /tmp/cog
uv run l3proc watch ~/workspace/lamula-jobs/f0-run/products --once --no-publish -o /tmp/cogs
```

### 7. Equivalencia contra el feed oficial

La validación cuantitativa de toda la cadena: el mismo barrido por las dos vías tiene que decir
lo mismo. El lado de referencia ya está hecho y comprobado; falta el lado del job.

```bash
cd ~/workspace/lamula-jobs
f0/catalogo.py pairs KAMX <ayer> --product N0B      # elegir una pareja
f0/equivalencia.py referencia KAMX <hora> --dir ref
f0/equivalencia.py huella ref --salida ref.json
f0/equivalencia.py huella f0-run/products --salida job.json
f0/equivalencia.py comparar ref.json job.json
```

Usa un volumen **reciente**: el archivo de Level III solo llega a marzo de 2022, así que Irma,
Harvey y Michael no tienen referencia oficial contra la que comparar. Para esta puerta da igual
qué volumen sea; lo que se valida es la cadena, no la tormenta.

### 8. Aislamiento entre jobs

```bash
# dentro del contenedor, después de un job de KAMX
change_radar -r khgx -S -R
mrpg -p -v startup
# repetir pasos 4 y 5 con volúmenes de KHGX
```

**Puerta:** ni un solo producto de KAMX en el directorio del segundo job, y el `lat`/`lon` de
los productos nuevos es el de KHGX. Un producto filtrado es un fallo silencioso y es lo que
decide si D3 (runner persistente que recicla el ORPG) se sostiene.

### 9. Medir

Lo que pide [Límites y recursos](../operacion/limites-recursos.md): RAM pico, CPU media y pico,
duración real de doce volúmenes, bytes de productos crudos y de COGs. Con el pipeline live
corriendo en el mismo nodo, además, el retraso del `processor`.

```bash
docker stats --no-stream orpg-f0
du -sh f0-run/products /tmp/cogs
```

## Dónde va cada resultado

| Qué sale | Dónde se escribe |
|---|---|
| Un número medido | `docs/referencia/` con la fecha, y el script que lo reproduce en `f0/` |
| Un hecho del ORPG | `docs/referencia/orpg-hechos.md` |
| Una decisión nueva o revisada (D6) | `docs/alcance/decisiones.md`, con fecha y motivo |
| Una puerta que no pasa | `docs/alcance/pendientes.md`, y para el diseño antes de seguir |
| Un hallazgo que da para artículo | `linkedin/NN-titulo.md`, en el estilo de los siete que hay |

## Lo que no se toca

- **El build del ORPG no se modifica por motivos de licencia.** El asunto está en consulta con
  los dueños del código desde el 2026-11-02; hay dos borradores de correo en `correspondencia/`
  esperando revisión. Excluir directorios del build es una de las opciones sobre la mesa, no una
  decisión tomada.
- **La imagen del ORPG no sale de nuestra infraestructura** mientras eso no se resuelva.
- **No se escribe código del servicio** —runner, cola, API— hasta que F0 pase.
