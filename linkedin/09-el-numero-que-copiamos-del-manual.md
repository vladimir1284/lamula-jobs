# Post 09 — El número que copiamos del manual

**Hito:** Fase 0 de LAMULA Jobs. Dos ejecuciones completas de doce volúmenes, una con el fallo y otra sin él.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

En el post anterior conté que un producto de radar había llegado cortado sin que nadie avisara. Tenía una sospecha sobre la causa y la dejé escrita como sospecha. Esta semana la comprobé, y la causa es de las que dan vergüenza ajena.

El programa que recoge los productos da a cada uno **30 segundos** para llegar entero. Si no ha terminado, cierra la conexión y guarda lo que tenga. Ese plazo está escrito a fuego en el código. No se configura.

Lo que sí se configura es la velocidad del enlace por el que el sistema envía los productos. Y en la receta que seguimos, copiada de la documentación, la velocidad estaba en 100 kilobits por segundo. A esa velocidad, el producto de reflectividad —unos 400 kilobytes— tarda unos 32 segundos. Dos segundos más de lo que el receptor aguanta. Todos los productos pequeños pasaban de sobra; el grande se quedaba corto casi siempre.

Con la velocidad original del fichero, que la receta había rebajado sin motivo, el mismo producto tarda un par de segundos.

Los números, con doce volúmenes del huracán Irma por cada ejecución:

- **Enlace lento:** 8 de 12 productos de reflectividad truncados. Los cuatro completos lo fueron por casualidad de tiempos.
- **Enlace rápido:** 0 truncados. 106 productos decodificados, 0 fallos.

Tres cosas que me llevo, ninguna sobre radares:

**Un número copiado de un manual es una hipótesis.** El manual describía una instalación de ejemplo, con otras necesidades, y el 100 000 era razonable *para ella*. Nadie lo puso ahí para nosotros.

**Un fallo que depende de un tamaño y de un reloj parece azar.** Cuatro de doce se salvaron y eso lo hacía parecer intermitente. No lo era: era determinista, y solo lo vimos así cuando miramos *qué* fallaba (siempre el grande) y *a qué hora* (siempre a los 30 segundos exactos).

**Arreglar la causa no sustituye a vigilar el síntoma.** La velocidad ya está corregida, pero cada trabajo comprobará además que cada producto mida lo que su cabecera dice que mide. Si el fallo vuelve por otro camino, que se note el primer día y no el mes que viene.

Un detalle que me gusta: la herramienta que comprueba esto tiene veinte líneas. La que habría hecho falta para entender el fallo sin ella, bastantes más.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Software #Integracion #Radar #NEXRAD #Calidad #Debugging
