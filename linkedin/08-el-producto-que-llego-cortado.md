# Post 08 — El producto que llegó cortado, y nadie lo dijo

**Hito:** Fase 0 de LAMULA Jobs. Primera ejecución real del software del radar dentro de un contenedor.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

**Contexto, para quien llegue aquí sin haber leído los anteriores.** Estados Unidos tiene unos 160 radares meteorológicos (la red NEXRAD). Cada cinco minutos, cada radar produce un *volumen*: un barrido completo de la antena a varias inclinaciones, en bruto (se llama Level II). El Servicio Meteorológico Nacional (NWS) convierte esos volúmenes en *productos* —mapas de lluvia, de viento, de granizo— con un programa llamado **ORPG** (Open Radar Product Generator), que distribuye públicamente dentro de un paquete llamado CODE.

Estamos jugando con ese software. El experimento: darle volúmenes históricos —el huracán Irma, por ejemplo— y ver si podemos montar un servicio en el que alguien elija un evento pasado y lo vea procesado con el programa real, no con una imitación. Es un laboratorio, no un producto ni nada oficial.

Esta semana lo ejecutamos por primera vez, con volúmenes del radar de Miami (KAMX). En la primera hora aparecieron tres cosas que ninguna lectura nos había dado.

**Una: me equivoqué al teclear, y el error no apuntaba a mi error.** El ORPG tiene un programa, `nbtcp`, que hace de usuario de red: se conecta y recoge los productos a medida que se generan. Decide cómo conectarse mirando el *último argumento* de la línea de comandos: si mide dos caracteres o menos es un número de enlace; si mide más, un nombre de máquina. Yo puse `1`. Falló con un mensaje sobre un fichero de configuración que no tenía nada que ver. Una línea del código fuente lo explicó, y nuestra receta ya decía lo correcto.
*Para llevarte:* cuando un error apunta a algo que no has tocado, pregúntate primero qué rama del programa has activado sin querer.

**Dos: la lista de reproducción que generaba nuestra herramienta no servía.** El ORPG reproduce volúmenes grabados con otro programa, `play_a2`, que acepta los ficheros de dos maneras: una lista explícita (`-p`) o un directorio (`-d`). Solo el directorio reconoce el formato en que el archivo público de AWS distribuye los volúmenes; la lista los marca todos con el mismo tipo, sin mirar qué son. El síntoma es un error de descompresión que parece un fichero corrupto. No lo estaba: lo leíamos por la puerta equivocada.
*Para llevarte:* un «fichero corrupto» puede ser un fichero sano leído por el camino equivocado. Prueba el mismo fichero por otra ruta antes de culpar al fichero.

**Tres, la que me quita el sueño: un producto salió cortado y el sistema no dijo nada.** El producto principal de reflectividad declaraba en su cabecera 401 427 bytes. En disco había 399 360. Ni error ni aviso. `nbtcp` cierra la conexión cuando vence un temporizador, y si el producto va a medias, guarda lo que llegó y sigue. El siguiente producto del mismo tipo, completo, se decodificó bien y coincidía al byte con el del archivo oficial.

Un fichero truncado habría entrado en nuestro pipeline y habría fallado más tarde, lejos de la causa; o peor, habría dado una imagen con un trozo del mapa vacío que nadie sabría explicar.

La defensa es barata: la cabecera de cada producto dice cuánto debería medir, y comparar eso con el tamaño real son veinte líneas. Ya está escrita y es parte de lo que un trabajo tiene que pasar antes de darse por bueno.

Y una cuarta cosa, por honestidad: la opción de máxima velocidad de `play_a2`, que esperábamos que convirtiera una hora y media en minutos, no fue rápida. Dos volúmenes tardaron doce minutos, casi lo mismo que a ritmo real. Es una medida pequeña; la repetimos con doce volúmenes antes de concluir nada.

**Lo transferible:** cuando integras con un sistema que no controlas, *su ausencia de error no es éxito*. En cada paso, desde el primer día, mide lo que debería haber salido y compáralo con lo que salió.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Software #Integracion #Radar #NEXRAD #Calidad
