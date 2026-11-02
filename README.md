# lamula-jobs

Demo bajo demanda de la suite LAMULA: el cliente elige una secuencia de observaciones Level II,
un **ORPG real** (CODE B24.0r1.20) las procesa, y los productos Level III resultantes se ven en
una instancia dedicada del LAMULA-WebViewer.

El demo público actual enseña productos Level III que ya venían hechos desde el feed de
Unidata. Esto enseña la cadena entera: base data cruda, generación de productos,
almacenamiento y visualización.

Documentación completa:

```bash
uvx --with mkdocs-material mkdocs serve   # http://127.0.0.1:8000
```

O leer directamente bajo `docs/`:

- `docs/index.md` — visión general
- `docs/alcance/contexto.md` — qué es, qué no es, relación con los otros repos
- `docs/alcance/decisiones.md` — decisiones congeladas
- `docs/arquitectura/ciclo-runner.md` — un job de principio a fin
- `docs/implementacion/fases.md` — plan de trabajo, empezando por la Fase 0
- `docs/referencia/orpg-hechos.md` — lo verificado del CODE Guide, para no releer los PDF
- `docs/referencia/licencia.md` — qué se puede y qué no con el CODE; léelo antes de abrir esto a terceros

## Estado

**Solo scaffold de documentación.** La Fase 0 no se ha ejecutado: nadie ha automatizado
todavía `nbtcp` ni ha comprobado que un volumen de AWS recorra la cadena entera. Hasta
entonces, todo esto es diseño sobre papel.

## Repos hermanos

`radar-orpg-dev` (imagen del ORPG), `nexrad-l3-pipeline` (decodificación, COG, contrato de
datos), `lamula-webviewer` (visor), `lamula-process` (catálogo de AWS y de sitios),
`lamula-rcp` (futura fuente de Level II propio).
