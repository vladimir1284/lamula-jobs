# LAMULA Jobs

Demo bajo demanda de la suite LAMULA completa: un cliente elige una secuencia de
observaciones Level II, nosotros las pasamos por un **ORPG real** (CODE B24.0r1.20, el mismo
software que corre en un WSR-88D operativo), y la salida entra por el pipeline de
`nexrad-l3-pipeline` hasta un espacio dedicado del `lamula-webviewer` donde el cliente ve sus
productos.

Lo que el demo público de `nexrad-l3-pipeline` enseña hoy son productos Level III que **ya
venían hechos** desde el feed de Unidata. Esto enseña la cadena entera: base data cruda →
generación de productos → almacenamiento → visualización. Es decir, el producto que se vende,
no una parte de él.

```mermaid
flowchart LR
  F[Fuente de volúmenes<br/>Level II] --> S[(Staging R2)]
  S --> R[job-runner<br/>ORPG + pipeline]
  R --> B[(R2 demo)]
  R --> P[(Postgres: schema del job)]
  B --> V[viewer-demo]
  P --> V
```

Empieza por [Contexto y alcance](alcance/contexto.md), sigue por
[Decisiones de diseño](alcance/decisiones.md).

!!! danger "Repo recién creado"
    Solo existe el scaffold de documentación. **La Fase 0 no se ha ejecutado**: nadie ha
    automatizado todavía `nbtcp` ni ha comprobado que un volumen de AWS recorre la cadena
    entera. Hasta que F0 pase, todo lo de aquí es diseño sobre papel. Ver
    [Fases](implementacion/fases.md).
