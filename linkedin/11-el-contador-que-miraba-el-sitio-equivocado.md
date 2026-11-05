# Post 11 — El contador que miraba el sitio equivocado

**Hito:** Fase 0 de LAMULA Jobs. Intento de acelerar la reproducción de volúmenes de radar.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

**Contexto.** Estamos experimentando con el ORPG, el software con el que el Servicio Meteorológico Nacional de EEUU convierte los datos crudos de sus radares (NEXRAD) en productos meteorológicos. El plan es un servicio que reproduzca eventos pasados con el programa real. Un problema práctico: procesar un solo volumen de radar tarda unos seis minutos, y un evento tiene cientos. Queríamos saber si se podía ir más rápido.

**La idea que parecía gratis.** La herramienta de reproducción del ORPG, `play_a2`, lee los volúmenes grabados y se los da al ORPG a un ritmo controlado. Probé a saltármela: un pequeño programa propio que hace de *radar de mentira* y envía los datos al ORPG por el mismo canal por el que los enviaría un radar real, a la velocidad que yo elija.

Funcionó a medias, y lo interesante es cómo falló. A velocidad normal, bien. Al cuadruplicarla, salían 4 productos de 16. Al enviar sin freno, cero. Y el contador de «datos perdidos» del ORPG decía **cero** en todos los casos.

**Me creí el contador demasiado rato.** Pensé en un fallo de distribución, en un proceso que moría, en problemas de tiempos. Todo tenía sentido menos una cosa: si no se perdía nada, ¿por qué faltaban productos?

**La causa.** El contador miraba la primera etapa del ORPG, la que recibe los datos. La pérdida ocurría en la segunda: un proceso que corrige velocidades del viento (el desplegado de velocidades Doppler) leía de un búfer de 1500 mensajes, unos cuatro giros de antena. A ritmo rápido se quedaba atrás, y los datos se sobrescribían antes de que los leyera. Lo dejaba escrito en su propio registro, en otro fichero que yo no había abierto.

Subí el búfer de 1500 a 5000 mensajes, un cambio de configuración, y a cuatro veces la velocidad salieron los productos que tocaban, idénticos a los de la corrida lenta.

**Qué aprender de esto:**

**Un contador en cero solo prueba que ese contador no vio nada.** Antes de fiarte de él, comprueba que sabe detectar una pérdida: provoca una a propósito y mira si se mueve. Es el mismo error del post anterior con otro disfraz.

**Cuando faltan resultados, sigue el dato por cada etapa.** La pérdida estaba donde menos miraba, un paso después del único sitio con contador.

**Revisa dónde crees que está el límite.** Llevaba días dando por hecho que el sistema era lento por calcular. Era lento por esperar: el ritmo lo marcaba el control de flujo de la herramienta de reproducción, no la CPU.

Queda trabajo: el primer volumen sigue sin coincidir del todo con el de la herramienta oficial, y no sé aún por qué. Lo cuento cuando lo sepa.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Software #Depuración #Rendimiento #Radar #NEXRAD
