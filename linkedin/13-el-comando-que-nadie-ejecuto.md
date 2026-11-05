# Post 13 — El comando que nadie ejecutó

**Hito:** Fase 2 de LAMULA Jobs. Convertir la reproducción de radar en un servicio con cola.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

Lancé el proceso que consume la cola como comando del contenedor. El contenedor arrancó, `docker ps` lo mostraba sano, y el trabajo se quedó en la cola. Sin error, sin log, sin nada.

Perdí veinte minutos mirando la base de datos, los permisos y la red.

La causa: la imagen del software de radar trae su propio punto de entrada, que arranca sus servicios y se queda dormido. **Ignora el comando que le pasas.** El mío nunca corrió. Todo lo demás funcionaba, y por eso no había nada que fallara.

**Un sistema que no hace lo que le pides y no se queja es peor que uno que falla.** Lo que me habría ahorrado el rato es una alarma: si nadie reclama un trabajo en un minuto, algo avisa. Eso todavía no existe; está en la lista de pendientes.

**«Está arrancado» no es «está trabajando».** Lo único que prueba que un proceso trabaja es el trabajo terminado.

Segundo despiste del mismo día, por la misma familia de causa: una herramienta de radar escribía su log en el directorio donde se la lanzaba, y yo la lanzaba desde uno sin permiso de escritura. Salió con código 255 y un mensaje de una línea. Las herramientas antiguas hacen cosas implícitas con el directorio actual, y a un servicio le conviene darles uno propio por trabajo.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Software #Docker #Backend #Radar #Depuración
