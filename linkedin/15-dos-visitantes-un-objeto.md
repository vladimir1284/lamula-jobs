# Post 15 — Dos visitantes, un objeto

**Hito:** Fase 2 de LAMULA Jobs. Cada visitante lanza su propio trabajo de reproducción de radar.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

Cada trabajo tiene su schema, sus usuarios y su directorio. Parecía aislado. Al repasar cómo se nombran los ficheros que publica, vi que no lo estaba.

Los mapas que salen del procesamiento se guardan en un bucket con una ruta del tipo `radar/producto/año/mes/día/…`. Ninguna parte de esa ruta identifica al trabajo. Si dos visitantes piden el mismo radar y la misma hora, **escriben el mismo fichero**. El último gana, y cuando el primero borra su trabajo, borra el mapa que el segundo sigue viendo.

No lo vi en ninguna prueba, porque ninguna lanzaba dos trabajos iguales a la vez. Lo vi leyendo código.

Qué hicimos, en este orden:

1. **Un guardián.** El alta de un trabajo se rechaza si otro vivo cubre el mismo radar y horas. Feo, pero seguro. Queda anotado como decisión, con la condición para retirarlo.
2. **La petición correcta.** El arreglo real es un prefijo configurable en las rutas, vacío por defecto para no cambiar nada a quien ya usa el componente. Es un cambio pequeño, y es de otro repositorio, así que lo pedí con una incidencia en vez de tocarlo.

El coste mientras tanto es concreto: dos prospectos no pueden ver a la vez el mismo huracán con trabajos propios.

**El aislamiento hay que revisarlo por cada sitio donde se escribe, no por cada sitio donde se piensa en él.** Base de datos, usuarios y directorios estaban bien. El bucket era el cuarto sitio y el único sin dueño.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Arquitectura #Multitenancy #Almacenamiento #Backend #Radar
