# Post 10 — La prueba que pasaba sin probar nada

**Hito:** Fase 0 de LAMULA Jobs. Prueba de aislamiento entre dos radares.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

Una de las decisiones de diseño de nuestro servicio descansa en una pregunta concreta: si un mismo proceso de radar atiende primero un trabajo de Miami y después uno de Houston, ¿puede colarse algún producto de Miami en el resultado de Houston? Si la respuesta es sí, hay que levantar un proceso nuevo por trabajo, y eso cuesta minutos y dinero.

La prueba es simple. Se procesa Miami, se cambia de sitio, se procesa Houston, y se busca cualquier rastro de Miami.

Esta semana la hice y salió limpia: cero productos de Miami. Estuve a punto de escribir «pasa».

Lo que me detuvo fue mirar cuántos productos de **Houston** había. Tres. Y los tres eran mensajes de estado de 230 bytes, no productos de radar.

La prueba había «pasado» porque no había salido nada de nada. Pedí los volúmenes de Houston de la primera mitad del día, y ese radar no tiene volúmenes catalogados hasta las cuatro de la tarde. La herramienta de descarga me devolvió una lista vacía, sin error, y el reproductor dijo con toda calma que no encontraba ficheros. Un resultado correcto en el sentido más inútil posible: ausencia de Miami porque había ausencia de todo.

Repetí con volúmenes que sí existían. Dieciocho productos de Houston, todos con las coordenadas de Houston, ninguno con las de Miami. Y como control, pasé esos mismos dieciocho por la comprobación con las coordenadas de Miami y los rechazó los dieciocho. Ahora sí es una prueba: una que puede fallar y no falla.

Tres hábitos que me quedan:

**Una prueba de «no hay X» necesita demostrar que habría visto X.** Mi control negativo tardó diez segundos en escribirse y es lo único que convierte «no apareció» en «no existe».

**Mira el denominador.** «Cero fallos» sobre cero casos es una frase gramaticalmente correcta y no dice nada.

**Las herramientas que no fallan cuando no hacen nada son una trampa.** Una descarga que termina bien sin descargar nada produce justo este error. La mía ya falla con un mensaje claro.

El resultado honesto, con sus límites: un cambio de sitio, en una dirección, con carpetas de salida nuevas. Para el diseño que queremos es suficiente. Para una afirmación general, no lo es todavía.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Software #Testing #Calidad #Radar #NEXRAD
