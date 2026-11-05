# Post 13 — El comando que nadie ejecutó

**Hito:** Fase 2 de LAMULA Jobs. Convertir la reproducción de radar en un servicio con cola.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

**Contexto.** Estamos experimentando con el ORPG, el software con el que el Servicio Meteorológico Nacional de EEUU genera productos a partir de los datos crudos de sus radares (NEXRAD). El experimento es un servicio donde alguien pide reproducir un evento pasado: la petición entra en una cola, un *worker* (un proceso que vive dentro de un contenedor Docker, junto al ORPG) la recoge, reproduce los volúmenes y publica los mapas.

**Lo que pasó.** Lancé el worker como comando del contenedor. El contenedor arrancó, `docker ps` lo mostraba sano, y el trabajo se quedó en la cola. Sin error, sin log, sin nada. Perdí veinte minutos mirando la base de datos, los permisos y la red.

**La causa.** La imagen del ORPG trae su propio punto de entrada (`ENTRYPOINT` en Docker), un script que arranca los servicios del radar y se queda dormido. **Ignora el comando que le pasas.** Mi worker nunca corrió. Todo lo demás funcionaba, y por eso no había nada que fallara.

**Un sistema que no hace lo que le pides y no se queja es peor que uno que falla.** Lo que me habría ahorrado el rato es una alarma: si nadie reclama un trabajo en unos minutos, algo avisa.

**Ya la tenemos, y esto es lo que añadimos:**

- **Una alarma de cola.** Un comando, `jobs-admin health`, sale con error si hay un trabajo esperando más de cinco minutos o uno en marcha sin latido. Tiene una prueba con trabajos simulados. Todavía no está decidido quién la ejecuta ni por qué canal avisa, así que hoy detecta pero no avisa a nadie.
- **Un supervisor.** Un pequeño script que lanza el worker y lo relanza si muere, con pausa creciente para no girar en vano si falla al arrancar.

**La prueba que importaba:** con el ORPG real reproduciendo un volumen del radar de Miami, maté el worker con `kill -9`. El supervisor lo relanzó en 2 segundos. El trabajo seguía marcado como «en marcha» por un worker que ya no existía; pasado un plazo sin latidos (en la prueba lo bajé a 40 segundos; el valor de producción es 600), el barrido periódico lo devolvió a la cola con su espacio de datos vacío. El worker nuevo lo reclamó como segundo intento, limpió los procesos del ORPG que el worker muerto había dejado reproduciendo y lo terminó bien. Al acabar: ningún proceso de más, ningún schema ni usuario huérfano.

Un detalle que la prueba dejó a la vista: durante esos 40 segundos el ORPG del worker muerto siguió reproduciendo, sin nadie que lo gobernara. Con el plazo de producción serían diez minutos. Es inofensivo aquí, pero consume el único ORPG del contenedor.

**Qué aprender de esto:**

**«Está arrancado» no es «está trabajando».** Lo único que prueba que un proceso trabaja es el trabajo terminado. Pon la alarma sobre el resultado (trabajos que no avanzan), no sobre el proceso (contenedor sano).

**Cuando heredas una imagen, lee su punto de entrada.** Una imagen de terceros puede ignorar tu comando, y ningún aviso te lo dirá.

**Prueba el fallo de verdad, no el simulado.** El supervisor ya había pasado con un worker de mentira que moría cada segundo, y esa prueba falló: una señal de parada no cortaba la pausa. La prueba con el programa real encontró otra cosa distinta: el ORPG huérfano.

**Segundo despiste del mismo día,** de la misma familia: una herramienta de radar escribía su log en el directorio desde donde se la lanzaba, y yo la lanzaba desde uno sin permiso de escritura. Salió con código 255 y un mensaje de una línea. Las herramientas antiguas hacen cosas implícitas con el directorio actual: a un servicio le conviene darles uno propio por trabajo.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Software #Docker #Backend #Radar #Depuración
