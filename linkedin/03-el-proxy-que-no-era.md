# Post 03 — El atajo que parecía evidente y medía otra cosa

**Hito:** Fase 0 de LAMULA Jobs. Selección de casos preparados para el demo.
**Estado:** listo para publicar.

---

Teníamos que elegir, dentro de un día de huracán, la hora exacta que le enseñamos al cliente. Una hora, unos doce volúmenes de observación, lo más espectacular posible.

El problema es que averiguar cuál es la hora buena parecía caro. Cada volumen de radar ocupa unos veinte megabytes; un día son doscientos volúmenes y cuatro gigabytes. Descargarlos y decodificarlos todos para saber cuándo llovía más es un rato largo de red por cada caso del catálogo.

Y entonces aparece el atajo, que es de esos que dan ganas de contarlos antes de comprobarlos.

Los ficheros van comprimidos. La compresión funciona mal sobre datos con mucha información y muy bien sobre datos repetitivos. Un cielo despejado es un campo casi entero de "nada aquí": comprime muchísimo. Una tormenta es ruido estructurado en todas las celdas: comprime mal. Luego el tamaño del fichero, que el listado del almacén ya nos da gratis, debería crecer con la intensidad de la tormenta.

Suena bien. Es coherente. Y está mal.

La prueba fue barata, que es lo único que la salva de haber sido una suposición cara. Tomamos el día de un huracán en el radar de Tampa, doscientos seis volúmenes, y perfilamos uno de cada cuatro leyendo el patrón de barrido de cada uno.

Salieron dos poblaciones limpias:

- De medianoche a las 12:40, un patrón de barrido: mediana de 23,4 MB por volumen.
- De las 13:09 a medianoche, otro patrón: mediana de 18,8 MB.

El huracán tocó tierra por la tarde. La tormenta más fuerte está en el tramo de los ficheros **pequeños**.

Lo que domina el tamaño no es cuánta lluvia hay delante, sino cuántos cortes de elevación hace la antena y a qué resolución los muestrea: el patrón de barrido. Dos patrones distintos producen volúmenes de tamaños distintos aunque la atmósfera sea idéntica, y la diferencia entre patrones es mayor que la diferencia entre llover y no llover. Elegir por bytes elige el patrón más caro, no la tormenta más fuerte.

Rematamos la comprobación midiendo de verdad, que es lo que había que hacer desde el principio: decodificar el barrido más bajo de volúmenes muestreados a lo largo del día y contar qué fracción del área a menos de 150 km supera los 35 dBZ. La curva sale inequívoca y va en sentido contrario al tamaño:

```
13:16   20,6 MB   18,9 % de área con eco fuerte
16:35   19,8 MB   22,4 %
19:54   18,3 MB   20,4 %
22:08   16,6 MB   32,5 %   ← pico
```

El momento de máxima actividad es el de los ficheros más pequeños del día. El atajo no estaba un poco sesgado: estaba anticorrelacionado.

Dos cosas me parecen dignas de quedarse.

La primera es que el razonamiento era correcto y la conclusión falsa. Sí es verdad que la tormenta comprime peor que el cielo despejado. Lo que pasa es que hay una segunda variable, que no estaba en el razonamiento, con más peso que la primera. Un proxy no falla por ser absurdo; falla por estar midiendo también otra cosa que no controlas.

La segunda es el precio de comprobarlo. Verificar el atajo costó unas peticiones HTTP de 64 KB —el patrón de barrido viaja en los primeros kilobytes de cada volumen— y un rato de descargas para la medida de contraste. Si lo hubiéramos dado por bueno, el catálogo entero de casos preparados habría quedado apuntando a las horas tranquilas de cada huracán, y el error se habría visto el día de la primera demostración, delante de alguien.

El atajo sigue en la herramienta, por cierto. Pero renombrado y documentado por lo que sí mide: cuántos bytes hay que mover en el peor caso, que para dimensionar la descarga y el almacenamiento vale perfectamente.

#Radar #NEXRAD #DatosAbiertos #Medir #IngenieriaDeDatos
