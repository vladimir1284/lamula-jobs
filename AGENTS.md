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

## Reglas que no se negocian

- **El runner no sabe de dónde vienen los ficheros.** Recibe claves en staging. Meter AWS (o
  cualquier otra fuente) dentro del runner rompe la segunda fuente ya comprometida.
- **El contrato de datos es del pipeline.** `db/pg_migrations/0001_init.sql` de
  `nexrad-l3-pipeline` se aplica tal cual en el schema del job. Aquí no se migra ese schema ni
  se le añaden columnas.
- **Nada del plano demo escribe en los almacenes de producción.** Base distinta, bucket
  distinto, siempre.
- **Un job termina o falla, nunca cuelga.** Todo paso lleva timeout, y un runner muerto
  devuelve su job a la cola.
- **Las coordenadas se verifican.** Tras cada job, el `site_id` y el lat/lon que acaban en
  `radars` tienen que coincidir con los del job. Un `change_radar` que no surtió efecto no
  produce ningún error visible, solo un COG en el sitio equivocado.
- **Sin socket de Docker.** El runner es persistente y recicla el ORPG; no crea contenedores.

## Convenciones

- Python con `uv`, igual que `nexrad-l3-pipeline`. Nada de pip, venv ni poetry directos.
- Documentación en `docs/`, mkdocs-material, español, desplegada a Cloudflare Pages por
  `.github/workflows/docs.yml`.
- Las decisiones nuevas se añaden a `docs/alcance/decisiones.md` con fecha y motivo.
