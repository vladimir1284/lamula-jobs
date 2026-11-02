# Post 08 — El producto que llegó cortado, y nadie lo dijo

**Hito:** Fase 0 de LAMULA Jobs. Primera ejecución real del software del radar dentro de un contenedor.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

Llevábamos semanas diseñando un servicio que reproduce observaciones históricas de un radar por el software real de procesamiento y recoge los productos que salen. Todo sobre papel y sobre código fuente. Esta semana lo ejecutamos por primera vez, con dos volúmenes del huracán Irma, y en la primera hora nos encontramos tres cosas que ninguna lectura nos había dado.

**Una: el manual y el código tenían razón, y yo me equivoqué al teclear.** El programa que recoge los productos decide qué tipo de conexión usar mirando el *último argumento* de la línea de comandos: si mide dos caracteres o menos, es un número de enlace; si mide más, es un nombre de máquina. Yo puse `1`. Falló con un error sobre un fichero de configuración que no tenía nada que ver con el problema. Una línea del fuente lo explicó, y la receta que habíamos escrito ya decía lo correcto. Lección menor: cuando un error apunta a algo que no has tocado, mira primero qué rama del programa has activado sin querer.

**Dos: la lista de reproducción que nuestra herramienta generaba no servía.** El reproductor tiene dos formas de recibir ficheros, y solo una de ellas reconoce el formato en que el archivo público distribuye los volúmenes. En la otra, el código marca todos los ficheros con el mismo tipo, sin mirar qué son. El síntoma es un error de descompresión que parece un fichero corrupto. No lo estaba: estaba bien leído por la puerta equivocada. Nuestra herramienta de descarga escribía justo esa lista.

**Tres, y es la que me quita el sueño: un producto salió cortado y el sistema no dijo nada.** El producto principal de reflectividad declaraba en su cabecera 401 427 bytes. En disco había 399 360. Ni error, ni aviso. El programa de recogida cierra la conexión cuando vence un temporizador, y si el producto va a medias, guarda lo que llegó y sigue. El siguiente producto del mismo tipo, completo, se decodificó sin problemas y su contenido descomprimido coincidía al byte con el del archivo oficial.

Un fichero truncado habría entrado en el pipeline y habría fallado más tarde, lejos de la causa, o peor: habría producido una imagen con un trozo del mapa vacío que nadie sabría explicar.

La defensa es barata. La cabecera de cada producto dice cuánto debería medir; comparar eso con el tamaño real son veinte líneas. Ya está escrita, y ahora forma parte de la lista de comprobaciones que un trabajo tiene que pasar antes de darse por bueno.

Y una cuarta cosa, para ser honesto con lo que aún no sé: la opción de "máxima velocidad" que esperábamos que convirtiera una demostración de hora y media en unos minutos no fue rápida. Dos volúmenes tardaron doce minutos, casi lo mismo que a ritmo real. Es una medida pequeña. Estamos repitiéndola con doce volúmenes antes de sacar ninguna conclusión.

Lo transferible: cuando integras con un sistema que no controlas, **su ausencia de error no es éxito**. Mide lo que debería haber salido y compáralo con lo que salió, en cada paso, desde el primer día.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Software #Integracion #Radar #NEXRAD #Calidad
