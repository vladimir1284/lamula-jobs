# Post 10 — La prueba que pasaba sin probar nada

**Hito:** Fase 0 de LAMULA Jobs. Prueba de aislamiento entre dos radares.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

**Contexto.** Estamos experimentando con el ORPG, el software con el que el Servicio Meteorológico Nacional de EEUU convierte los datos crudos de sus radares (NEXRAD) en productos meteorológicos. La idea es un servicio que reproduzca eventos pasados con el programa real. Si varias personas lo usaran, cada una pediría un radar distinto: unas Miami (KAMX), otras Houston (KHGX).

**La pregunta de diseño.** Si un mismo ORPG procesa primero un trabajo de Miami y después uno de Houston, ¿puede colarse algún producto de Miami en el resultado de Houston? Si la respuesta es sí, hay que levantar un ORPG nuevo por trabajo, y eso cuesta minutos y dinero. Si es no, se puede reutilizar uno.

La prueba es simple: procesar Miami, cambiar de radar, procesar Houston y buscar cualquier rastro de Miami.

La hice y salió limpia: cero productos de Miami. Estuve a punto de escribir «pasa».

**Lo que me detuvo** fue mirar cuántos productos de **Houston** había. Tres. Y los tres eran mensajes de estado de 230 bytes, no productos de radar.

La prueba había «pasado» porque no había salido nada de nada. Pedí volúmenes de Houston de la primera mitad del día, y ese radar no tiene volúmenes catalogados hasta las cuatro de la tarde. Nuestra herramienta de descarga devolvió una lista vacía, sin error, y el reproductor del ORPG dijo con calma que no encontraba ficheros. Resultado correcto en el sentido más inútil posible: ausencia de Miami porque había ausencia de todo.

Repetí con volúmenes que sí existían. Dieciocho productos de Houston, todos con las coordenadas de Houston y ninguno con las de Miami. Y como control, pasé esos mismos dieciocho por la comprobación de coordenadas *de Miami*: los rechazó los dieciocho. Ahora sí es una prueba, porque puede fallar y no falla.

**Qué aprender de esto:**

**Una prueba de «no hay X» tiene que demostrar que habría visto X.** El control negativo tardó diez segundos en escribirse y es lo único que convierte «no apareció» en «no existe».

**Mira el denominador.** «Cero fallos» sobre cero casos es una frase correcta y no dice nada. Antes de celebrar un cero, pregunta sobre cuántos.

**Las herramientas que no fallan cuando no hacen nada son una trampa.** Una descarga que termina bien sin descargar produce justo este error. La nuestra ya falla con un mensaje claro cuando la lista sale vacía.

**Los límites del resultado, tal cual:** un cambio de radar, en una dirección (Miami → Houston), con carpetas de salida nuevas. Para el diseño que queremos basta. Para una afirmación general, todavía no.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Software #Testing #Calidad #Radar #NEXRAD
