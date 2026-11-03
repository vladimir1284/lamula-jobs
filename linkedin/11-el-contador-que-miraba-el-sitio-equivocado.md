# Post 11 — El contador que miraba el sitio equivocado

**Hito:** Fase 0 de LAMULA Jobs. Intento de acelerar la reproducción de volúmenes de radar.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

Reproducir un volumen de radar por nuestro sistema tarda unos seis minutos. Queríamos saber si se podía hacer más rápido, y probé una idea que parecía gratis: en vez de usar la herramienta de reproducción, hacer que el sistema crea que habla con un radar real, y mandarle los datos sin esperas.

Funcionó a medias, y lo interesante es cómo falló.

A velocidad normal, bien. Al cuadruplicarla, salían cuatro productos de dieciséis. Al enviar sin freno, cero. Y yo tenía un contador de «datos perdidos» que decía **cero** en todos los casos.

Me creí el contador una tarde entera. Pensé en un fallo de distribución, en un proceso que moría, en tiempos. Todo tenía sentido menos una cosa: si no se perdía nada, ¿por qué faltaban productos?

El contador miraba la primera etapa del sistema. La pérdida ocurría en la segunda: un proceso que corrige velocidades leía de un búfer de 1500 mensajes, unos cuatro giros de antena, y a ritmo rápido se quedaba atrás y le pisaban los datos antes de leerlos. Lo dejaba escrito en su propio registro, en otro fichero que yo no había abierto.

Subí el búfer de 1500 a 5000 mensajes, un cambio de configuración, y a cuatro veces la velocidad salieron los productos que tocaban, idénticos a los de la corrida lenta.

Tres lecciones:

**Un contador en cero solo prueba que ese contador no vio nada.** Antes de fiarme de él tendría que haber comprobado que sabía detectar una pérdida. Es el mismo error de siempre con otro disfraz.

**Cuando faltan resultados, sigue el dato hasta cada etapa.** La pérdida estaba donde menos miraba.

**El límite no estaba donde lo suponía.** Llevaba semanas dando por hecho que el sistema era lento por calcular. Era lento por esperar.

Queda trabajo por hacer: el primer volumen sigue sin coincidir del todo con el de la herramienta original, y no sé aún por qué. Lo cuento cuando lo sepa.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Software #Depuración #Rendimiento #Radar #NEXRAD
