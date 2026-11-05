# Post 15 — Dos visitantes, un objeto

**Hito:** Fase 2 de LAMULA Jobs. Cada visitante lanza su propio trabajo de reproducción de radar.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

**Contexto.** Estamos experimentando con el ORPG, el software con el que el Servicio Meteorológico Nacional de EEUU genera productos a partir de los datos crudos de sus radares (NEXRAD). El experimento es un servicio donde alguien elige un evento pasado, lo reproducimos con el programa real y ve el resultado en un visor de mapas. Cada petición es un *trabajo*, con su propio espacio en la base de datos y sus propios usuarios.

**El diseño parecía aislado.** Al repasar cómo se nombran los ficheros que se publican, vi que no lo estaba.

Los mapas que salen del procesamiento (imágenes georreferenciadas, en formato COG) se guardan en un bucket de almacenamiento de objetos con una ruta del tipo `radar/producto/año/mes/día/…`. Esa ruta la construye nuestro pipeline de procesamiento, que se diseñó antes para otro uso: procesar el feed público de forma continua, donde dos escritores del mismo fichero son el mismo dato. Nada en la ruta identifica al trabajo.

Si dos visitantes piden el mismo radar y la misma hora, **escriben el mismo fichero**. El último gana. Y cuando el primero borra su trabajo, borra el mapa que el segundo sigue viendo.

**No lo vi en ninguna prueba**, porque ninguna lanzaba dos trabajos iguales a la vez. Lo vi leyendo el código que construye las rutas, que es dónde hay que mirar cuando preguntas «¿dónde se escribe algo sin que yo lo controle?».

**Qué hicimos, en este orden:**

1. **Un guardián.** El alta de un trabajo se rechaza (HTTP 409) si otro vivo cubre el mismo radar y las mismas horas. Es feo, pero seguro. Queda anotado como decisión con la condición para retirarlo.
2. **La petición correcta.** El arreglo real es un prefijo configurable en las rutas, vacío por defecto para no cambiar nada a quien ya use el componente. Es un cambio pequeño, pero es de otro repositorio, así que lo pedimos como incidencia en lugar de tocar el código.

El coste mientras tanto es concreto: dos visitantes no pueden ver a la vez el mismo huracán con trabajos propios.

**Qué aprender de esto:**

**El aislamiento se revisa por cada sitio donde se escribe, no por cada sitio donde se piensa en él.** Base de datos, usuarios y directorios estaban bien. El bucket era el cuarto sitio y el único sin dueño. Haz la lista de todos los lugares donde tu sistema escribe estado y pregunta de cada uno: ¿qué parte de su nombre dice a quién pertenece?

**Cuando reutilizas un componente en un contexto nuevo, sus suposiciones implícitas vienen con él.** El pipeline suponía un solo escritor por ruta. Era cierto en su origen y dejó de serlo al cambiar de uso.

**Un guardián temporal necesita una condición de retirada escrita.** Si no, se queda para siempre. El nuestro se retira cuando el pipeline acepte el prefijo.

**Pide el arreglo a quien es dueño del código.** Una incidencia con el problema, la propuesta y el motivo cuesta menos que una bifurcación que haya que mantener.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Arquitectura #Multitenancy #Almacenamiento #Backend #Radar
