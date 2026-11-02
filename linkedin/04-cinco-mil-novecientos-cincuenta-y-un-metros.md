# Post 04 — Un radar a 5951 metros sobre el nivel del mar

**Hito:** Fase 0 de LAMULA Jobs. Hallazgo colateral en el pipeline de producción.
**Estado:** listo para publicar.

---

El hallazgo de hoy no lo buscaba. Estaba comprobando otra cosa: que el catálogo de emplazamientos que usamos para configurar el radar del demo coincide con lo que después aparece en el producto generado. Es una verificación aburrida y por eso valía la pena hacerla, porque si el emplazamiento no cuadra, el resultado sale en el sitio equivocado del mapa sin dar ningún error.

Latitud y longitud cuadraban al milésimo de grado. La altura no.

Nuestro catálogo dice que el radar de Miami está a 4,27 metros sobre el nivel del mar. El producto dice 111. Veinticinco veces más.

La primera hipótesis fue la obvia: son unidades distintas. 111 pies son 33,8 metros, y un radar costero sobre una torre de unos treinta metros encaja perfectamente con una cota de terreno de 4,27. La explicación es coherente, pero coherente no es verificado: con un solo caso, cualquier factor cercano a tres explica cualquier cosa.

Así que fui a buscar el caso que discrimina. Albuquerque: un radar en terreno alto, a 1789 metros según el catálogo. Si el campo estuviera en metros, el producto diría algo cercano a 1800. Si estuviera en pies, diría algo cercano a 5900.

Dijo 5951. Que son 1814 metros. Cota del terreno más torre, otra vez.

Dos sitios con tres órdenes de magnitud de diferencia entre ellos, los dos cuadrando con el mismo factor de conversión. El campo está en pies, está documentado así en la especificación de interfaz del producto, y la librería que lo decodifica lo entrega tal cual, sin convertir, con una descripción que no menciona unidades.

Nuestro pipeline lo guarda en una columna llamada `height_m`.

Hasta aquí es un error de etiqueta y no quita el sueño. Lo que lo convierte en un error de cálculo está tres módulos más allá: el mosaico multi-radar usa esa altura para calcular a qué altitud va el centro del haz a cada distancia, y pondera cada píxel según eso. Un radar que mira una tormenta desde muy arriba la está viendo por encima de la parte que importa, y debe pesar menos. La referencia del peso está en 4 kilómetros.

Para el radar de Miami el error son 78 metros sobre una referencia de 4000. No se nota, y por eso lleva meses sin notarse.

Para Albuquerque el error son **4,1 kilómetros**. Ese radar entra en el mosaico declarando que su antena está por encima de la altura de referencia completa, y su peso se hunde en todo su dominio. No da error, no aparece en ningún log, no rompe ningún test: simplemente, en cada solape, el radar de montaña pierde contra el vecino que no lo merece.

Tres cosas que me llevo.

La primera es sobre qué caso de prueba elegir. Con el radar de Miami, el error era de 78 metros: invisible, y hasta plausible como diferencia entre "cota del terreno" y "altura de antena". El caso que lo delata es el que maximiza la magnitud de la variable sospechosa. Si verificas unidades, busca el extremo, no el típico.

La segunda es sobre los nombres. El error completo cabe en el sufijo de una variable. `height` sin unidad en la librería, `height_m` en nuestro lado, y nadie mintió: uno no dijo nada y el otro supuso. En código numérico, el nombre de la variable es parte del tipo, y una conversión que no existe no deja rastro en ningún sitio donde mirar.

La tercera es que el error lo encontró una tarea que no iba de eso. Iba de preparar un demo. La verificación cruzada entre dos fuentes que deberían decir lo mismo —nuestro catálogo y el producto decodificado— es barata, y encuentra cosas que ningún test unitario encuentra, porque un test unitario comprueba que el código hace lo que el autor creía, y aquí el autor creía que el campo venía en metros.

#Radar #NEXRAD #Python #Unidades #CalidadDeDatos
