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
