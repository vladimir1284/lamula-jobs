# Post 02 — Perfilar 30 años de archivo de radar sin descargarlo

**Hito:** Fase 0 de LAMULA Jobs. Medida del catálogo público antes de escribir el selector de casos.
**Estado:** listo para publicar.

---

Para el demo bajo demanda que estamos montando, el cliente elige una tormenta del pasado y nosotros la procesamos con un ORPG real. La parte bonita es el procesamiento. La parte que decide si el demo es viable es mucho más tonta: ¿qué hay exactamente en el archivo público, y cuánto cuesta servirlo?

Había cinco huracanes candidatos para el menú de casos preparados —Irma, Harvey, Michael, Ian, Milton— y cero números sobre ellos. Así que antes de diseñar nada, a medir.

**El problema de medir.** Lo que hace falta saber de cada volumen de observación es cuándo se tomó, cuánto ocupa y con qué patrón de barrido se observó. Lo primero y lo segundo vienen en el listado del bucket. Lo tercero va dentro del fichero. Y un volumen de huracán ocupa veinte megabytes.

Seis horas de tormenta son unos sesenta volúmenes. Cinco casos, trescientos volúmenes, seis gigabytes de descarga para leer un número entero de cada uno.

Hay un atajo, y está en el formato. Un volumen Level II moderno es una cabecera de 24 bytes seguida de registros comprimidos de forma independiente, y el primero de ellos es el registro de metadatos: configuración del radar, mapa de ruido, y el mensaje que describe el patrón de barrido completo. En los ficheros que medimos, ese primer registro ocupa **2,4 KB comprimidos**.

O sea: una petición HTTP con cabecera `Range`, los primeros 64 KB por si acaso, se corta el bloque por su frontera exacta y se le pasa al decodificador un fichero sintético de cabecera + primer registro. Sale el patrón de barrido, la hora exacta y el identificador del radar.

Seis gigabytes se convierten en unos dos megabytes. Un día entero de un radar —trescientos volúmenes— se perfila en el tiempo que tarda en cargar una página.

**Lo que apareció al mirar.** Tres cosas que cambian el diseño:

La primera: el archivo tiene prefijos de año desde 1991, y el menú de huracanes no necesita ninguna fuente nueva ni ningún trato con nadie. Pero —y esto es lo que había que mirar— el archivo antiguo no sirve. El software de procesamiento que usamos espera el formato moderno de mensajes, y el archivo guarda cada año en el formato de su época: hasta 2012 la mayoría de los radares están en una versión anterior, incompatible. El catálogo que de verdad podemos ofrecer empieza, según el radar, entre 2012 y 2014. Miami cruza en 2012, Houston en 2013, Valparaiso en 2014. Son tres fechas distintas para tres radares, en el mismo bucket.

Hay un detalle más que habría costado una tarde de depuración: entre 2013 y 2015 los ficheros del formato moderno están además envueltos en gzip, y el filtro obvio por sufijo —quedarse con lo que acaba en la versión buena— los descarta silenciosamente. Y aparece alguna versión suelta que no esperábamos: un radar, un solo año, en una versión posterior que nadie más usa. Un filtro de lista blanca, no de lista negra.

La segunda: Harvey cambia de patrón de barrido a mitad de la ventana que íbamos a ofrecer. Pasa de un patrón a otro una hora y media después del inicio. Era una de las preguntas abiertas de diseño —"¿qué hacemos si el cliente elige un rango con un cambio de patrón en medio?"— y estaba anotada como hipotética. No lo es: está dentro de uno de los cinco casos que queremos enseñar.

La tercera, la que más me gusta: los casos buenos traen datos rotos. El radar de Miami, durante Irma, produce cuatro volúmenes claramente cortos —diecinueve, quince, nueve megabytes donde los vecinos ocupan veinticinco— seguidos de huecos de entre 47 y 109 segundos, y más tarde un corte limpio de diez minutos. No son ficheros corruptos. Es un radar con un huracán de categoría 4 encima, reiniciándose. Las observaciones más vendibles del archivo son justo las que vienen con el servicio degradado.

Eso tiene una consecuencia operativa directa. Nuestro reproductor respeta el intervalo real entre volúmenes, porque acelerarlo arriesga perder datos. Un hueco de diez minutos en el archivo son diez minutos de servidor parado sin generar nada, pagados de la cuota del cliente. Conclusión: el trabajo se corta en el primer hueco que supere el doble de la cadencia normal de esa ventana, y se le avisa antes de confirmar.

Y una más, sobre las cuotas. Teníamos los límites expresados en número de volúmenes, que es lo que el cliente elige. Pero un volumen de huracán ocupa de doce a veinticinco megabytes y uno de día tranquilo menos de seis. El mismo límite en volúmenes permite mover cuatro veces más datos según el tiempo que hiciera. Las cuotas necesitan también un tope en bytes.

Ninguno de estos cuatro hallazgos requirió levantar un contenedor. Son un script de trescientas líneas y un rato de peticiones HTTP, y entre los cuatro han movido más el diseño que la semana anterior de diagramas.

La moraleja, si hay alguna: antes de diseñar sobre un conjunto de datos, mídelo. Y si el formato está bien hecho —y los formatos de radar lo están, llevan décadas de oficio encima—, casi siempre hay una manera de medirlo sin bajártelo entero.

#Radar #NEXRAD #DatosAbiertos #Python #IngenieriaDeDatos
