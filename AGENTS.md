# Instrucciones para el agente de desarrollo

## Antes de escribir código

Lee, en este orden:

1. `docs/alcance/contexto.md` — qué es y qué no es este servicio, y cómo se relaciona con los
   otros cuatro repos del equipo.
2. `docs/alcance/decisiones.md` — decisiones congeladas. **Ninguna se revierte sin discutirlo.**
3. `docs/alcance/pendientes.md` — huecos abiertos.
4. `docs/implementacion/fases.md` — el plan de trabajo.
5. `docs/referencia/orpg-hechos.md` antes de tocar cualquier cosa del ORPG. Está ahí para no
   tener que releer 197 páginas de PDF ni inventarse opciones de comando.

## Lo primero que hay que hacer

La **Fase 0**, a mano, en un contenedor: un volumen real de `unidata-nexrad-level2` recorriendo
`change_radar` → `mrpg -p startup` → `nbtcp` → `play_a2` → `l3proc process`. Si `nbtcp` no se
deja automatizar o `mrpg -p startup` no aísla un job del siguiente, el diseño cambia antes de
escribir el servicio, no después.

El instrumental está en `f0/` y su `README.md` dice qué parte ya está respondida sin contenedor
y qué parte falta. Descargar volúmenes y escribir la playlist es `f0/catalogo.py fetch`.

**Si estás en una máquina con Docker, empieza por
`docs/implementacion/f0-ejecucion.md`**: tiene los comandos literales en orden, las puertas de
cada paso y dónde se anota cada resultado. F0 no necesita Postgres, ni R2, ni el Swarm.

## Estado al 2026-11-02 — por dónde seguir

Esta sección es el punto de partida de la próxima sesión. **Todo lo que hace falta saber está en
el repo**: no hay notas, medidas ni acuerdos guardados fuera de aquí.

**La Fase 0 se ejecutó el 2026-11-02** en un contenedor (imagen local `orpg-prod:b24`, contenedor
`orpg-f0`). Las puertas, una a una, con su evidencia en `docs/referencia/`:

| Puerta | Resultado |
|---|---|
| `nbtcp -A -b` sin terminal | **Pasa.** El último argumento tiene que ser el hostname |
| Encabezado WMO de 30 B | **Pasa** con `-A`; originador `KMFL` para KAMX, `KHGX` para HGX |
| Coordenadas del sitio | **Pasa**, `f0/coordenadas.py` con control negativo |
| Aislamiento KAMX → KHGX (D3) | **Pasa**, con límites (un cambio, una dirección) |
| `l3proc` digiere los productos | **Pasa**: 106 de 106 en 12 volúmenes |
| Equivalencia contra el feed oficial | **Parcial**: N0B, EET, DVL, NMD iguales; N0G y NVW con ≥4 volúmenes; DAA converge; DTA y los ids de NST no, con 13 min de historia |
| Velocidad (D6) | **Medida**: los tres modos iguales en productos y ~80 min por 12 volúmenes |
| Recursos | **Parcial**: un volumen (125 % de CPU de pico, 790 MiB); falta con el pipeline live en el nodo |

Hallazgos que cambian el diseño, todos en `docs/referencia/orpg-hechos.md`:
`play_a2 -p` no lee el formato del bucket (usar `-d`); `nbtcp` trunca en silencio a los 30 s y la
causa era `LR=100000` (D11); `l3proc watch` consume su entrada; `mrpg startup` no sale; `GSM…`,
`P173_…` y `RR_…` no son productos.

**Lo que NO está hecho de F0:** la equivalencia no se midió con muchos volúmenes de historia, el
retraso del `processor` con el pipeline live, y la repetición de cada modo (hay una sola corrida
por modo). **No se ha escrito código del servicio.** Siguiente paso natural: F1, una vez el dueño
decida D6 y revise lo de abajo.

Estado de las máquinas: el contenedor `orpg-f0` sigue arriba y `f0-run/` (no versionado, ~1 GB)
tiene volúmenes y productos. `docs/implementacion/plan-autonomo.md` dice qué se hizo sin supervisión.

### Esperando al dueño del producto

Nada de esto se ejecuta por iniciativa propia:

| Qué | Dónde está |
|---|---|
| Dos borradores de consulta de licencia, sin enviar | `correspondencia/` — NWS y Universidad de Oklahoma. La dirección de OU está sin rellenar a propósito: se busca en ou.edu/otc, no se inventa |
| D6 (velocidad de reproducción): ya medida, los tres modos iguales y ~80 min por 12 volúmenes; **decide el dueño** | `docs/referencia/velocidad-reproduccion.md` |
| `-A` con el enrutado real del NWS, o parchear el pipeline con un `site_id` explícito | `docs/referencia/contrato-pipeline.md` |
| Umbral de huecos, `max_bytes` por job, texto del formulario de acceso | `docs/alcance/pendientes.md` |
| Los diez artículos de `linkedin/`, sin publicar: describen un demo comercial sobre el CODE | `linkedin/` — el 07 lleva nota explícita |

### Lo que ya salió de este repo

- **Issue abierto** en `nexrad-l3-pipeline`:
  [#8](https://github.com/vladimir1284/nexrad-l3-pipeline/issues/8), la altura del radar
  guardada en pies dentro de `height_m`. No se ha tocado ese repo; solo se reportó.
- Los demás cambios en repos ajenos siguen siendo propuestas, listados en
  `docs/alcance/pendientes.md`.

## Reglas que no se negocian

- **El runner no sabe de dónde vienen los ficheros.** Recibe claves en staging. Meter AWS (o
  cualquier otra fuente) dentro del runner rompe la segunda fuente ya comprometida.
- **El contrato de datos es del pipeline.** Las migraciones de `db/pg_migrations/` de
  `nexrad-l3-pipeline` se aplican tal cual en el schema del job —todas, también la del
  mosaico—. Aquí no se migra ese schema ni se le añaden columnas.
- **Nada del plano demo escribe en los almacenes de producción.** Base distinta, bucket
  distinto, siempre.
- **Un job termina o falla, nunca cuelga.** Todo paso lleva timeout, y un runner muerto
  devuelve su job a la cola.
- **Las coordenadas se verifican.** Tras cada job, el `site_id` y el lat/lon que acaban en
  `radars` tienen que coincidir con los del job. Un `change_radar` que no surtió efecto no
  produce ningún error visible, solo un COG en el sitio equivocado.
- **Sin socket de Docker.** El runner es persistente y recicla el ORPG; no crea contenedores.
- **La imagen del ORPG no se comparte con nadie de fuera** mientras no se resuelva lo de
  `docs/referencia/licencia.md`. Contiene código de la Universidad de Oklahoma con cláusula no
  comercial y código de MIT Lincoln Laboratory reproducible solo por o para el gobierno de
  EEUU.
- **No modifiques el build del ORPG por motivos de licencia.** El asunto está en consulta con
  los dueños del código desde el 2026-11-02. Excluir directorios del build es una de las
  opciones sobre la mesa, no una decisión tomada; proponerla está bien, ejecutarla por tu
  cuenta no. Los dos borradores de consulta están en `correspondencia/`, pendientes de que el
  dueño del producto los revise y los envíe.

## Convenciones

- Python con `uv`, igual que `nexrad-l3-pipeline`. Nada de pip, venv ni poetry directos.
- Documentación en `docs/`, mkdocs-material, español, desplegada a Cloudflare Pages por
  `.github/workflows/docs.yml`.
- Las decisiones nuevas se añaden a `docs/alcance/decisiones.md` con fecha y motivo.
- Lo que se mide o se comprueba va a `docs/referencia/` con la fecha de la medida, y el script
  que lo reproduce a `f0/`. Un número sin forma de repetirlo envejece mal.
