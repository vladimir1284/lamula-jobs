# Post 09 — El número que copiamos del manual

**Hito:** Fase 0 de LAMULA Jobs. Dos ejecuciones completas de doce volúmenes, una con el fallo y otra sin él.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

**Contexto.** Estamos probando el ORPG, el programa con el que el Servicio Meteorológico Nacional de EEUU convierte los datos crudos de sus radares (NEXRAD) en productos como mapas de reflectividad. Le damos volúmenes históricos del huracán Irma y recogemos lo que genera, para ver si se puede montar un servicio de reproducción de eventos pasados. Es un laboratorio, con el software que el NWS distribuye públicamente.

En el post anterior conté que un producto había salido cortado sin que nadie avisara. Dejé escrita una sospecha sobre la causa. Esta semana la comprobé, y es de las que dan vergüenza ajena.

**El mecanismo.** El programa que recoge los productos del ORPG, `nbtcp`, da a cada uno **30 segundos** para llegar entero. Pasado ese plazo cierra la conexión y guarda lo que tenga. El plazo está escrito a fuego en el código; no se configura.

Lo que sí se configura es la velocidad del enlace por el que el ORPG entrega los productos. En la receta que seguíamos, copiada de la documentación, estaba en 100 kilobits por segundo. El producto de reflectividad pesa unos 400 kilobytes, y a esa velocidad tarda unos 32 segundos: dos más de lo que el receptor aguanta. Los productos pequeños pasaban de sobra; el grande se quedaba corto casi siempre. Con la velocidad original del fichero de configuración (1,5 Mbit/s), que la receta había rebajado sin decir por qué, tarda un par de segundos.

**Los números**, con doce volúmenes de Irma por ejecución:

- Enlace lento: 8 de 12 productos de reflectividad truncados. Los cuatro completos lo fueron por casualidad de tiempos.
- Enlace rápido: 0 truncados. 106 productos decodificados, 0 fallos.

**Qué aprender de esto**, ninguna cosa sobre radares:

**Un número copiado de un manual es una hipótesis.** La documentación describía una instalación de ejemplo, con otras necesidades, y 100 000 era razonable *para ella*. Nadie lo puso ahí pensando en nosotros. Antes de heredar un valor, pregunta para qué escenario se eligió.

**Un fallo que depende de un tamaño y de un reloj parece azar.** Cuatro de doce se salvaron, y eso lo hacía parecer intermitente. Era determinista. Solo lo vimos al mirar *qué* fallaba (siempre el grande) y *cuándo* (siempre a los 30 segundos exactos). Si un fallo «intermitente» tiene un patrón en el tamaño o en el tiempo, no es intermitente.

**Arreglar la causa no sustituye a vigilar el síntoma.** La velocidad ya está corregida, pero cada trabajo comprueba además que cada producto mida lo que su cabecera dice. Si el fallo vuelve por otro camino, que se note el primer día y no el mes que viene.

Un detalle que me gusta: la herramienta que hace esa comprobación tiene veinte líneas. Entender el fallo sin ella habría costado bastantes más.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Software #Integracion #Radar #NEXRAD #Calidad #Debugging
