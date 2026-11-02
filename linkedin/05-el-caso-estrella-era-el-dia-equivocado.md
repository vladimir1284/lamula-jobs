# Post 05 — El caso estrella del demo era el día equivocado

**Hito:** Fase 0 de LAMULA Jobs. Selección final de los casos preparados.
**Estado:** listo para publicar.

---

Un demo de radar meteorológico se vende con tormentas reconocibles. Habíamos elegido cinco huracanes conocidos y, para cada uno, una ventana de seis horas alrededor de la hora en que tocó tierra. Parece la decisión más segura del proyecto: la recalada es el momento del que todo el mundo se acuerda.

Luego medimos cada ventana —decodificar el barrido más bajo de volúmenes repartidos por el día y contar qué fracción del área a menos de 150 km del radar supera los 35 dBZ— y salieron dos sorpresas.

La pequeña: en cuatro de los cinco casos, el máximo no caía en el centro de la ventana sino cerca del borde. La recalada y el máximo de eco **visto por ese radar concreto** no son el mismo instante, y no tienen por qué serlo. El ojo toca tierra donde toca; el radar ve su mejor imagen cuando la tormenta le pasa cerca, que puede ser tres horas antes o cuatro después.

La grande: uno de los cinco casos estaba directamente en el día equivocado.

Harvey, radar de Houston. La ventana apuntaba a la madrugada de la recalada. Medido: el radar veía, como mucho, un 15 % del área con eco fuerte, y el pico de ese día es peor que el valle del siguiente. Razón, obvia una vez que la miras: Harvey tocó tierra a unos 200 kilómetros de Houston. Esa noche, el radar que estábamos enseñando miraba mayormente el borde de la tormenta.

Lo que todo el mundo recuerda de Harvey en Houston no es la recalada: es la inundación, que fue al día siguiente. Medido ese día: 36,6 % de área con eco fuerte en el pico, el doble largo, y entre un 2 % y un 3 % del área por encima de 50 dBZ durante cinco horas seguidas, que es convección profunda sostenida. Además es el caso que mejor luce los productos de acumulación de lluvia, porque fue precisamente una inundación.

Es decir: el caso que íbamos a enseñar existía, era real, estaba bien etiquetado, y era el aburrido.

Lo que me parece interesante es de qué tipo es el error. No es un bug: ninguna línea de código estaba mal. No es un error de datos: el archivo tenía exactamente lo que decía tener. Es una suposición editorial —"la recalada es el momento bueno"— que nadie formuló en voz alta, que suena a conocimiento de dominio, y que resulta ser un enunciado sobre meteorología que se puede comprobar. Lo que no se puede es comprobarlo sin mirar los datos.

Y tenía además la forma más peligrosa que puede tener un error: ninguna. Un demo con el Harvey del día 26 habría funcionado perfectamente. Los productos se habrían generado, el visor los habría pintado, la línea de tiempo habría avanzado. El cliente habría visto lluvia modesta y bandas sueltas, habría dicho "ajá, muy interesante", y nos habríamos quedado sin saber por qué el huracán más famoso de la última década se veía tan soso en nuestra pantalla.

El coste de comprobarlo fue un script de ochenta líneas y un rato de descargas por caso. Lo dejamos en el repositorio como herramienta, no como script de usar y tirar, porque la pregunta "¿cuál es la hora buena de este evento?" se la vamos a hacer a cada caso nuevo que entre en el catálogo.

Las cinco ventanas finales duran hora y media, traen entre 13 y 17 volúmenes y cuestan entre 80 y 88 minutos de procesamiento en tiempo real. Y las cinco están centradas donde está la tormenta, no donde estaba el titular.

#Radar #NEXRAD #Huracanes #Demo #Datos
