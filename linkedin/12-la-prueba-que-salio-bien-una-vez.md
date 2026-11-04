# Post 12 — La prueba que salió bien una vez

**Hito:** Fase 0 de LAMULA Jobs. Acelerar la reproducción de volúmenes de radar a cuatro veces la velocidad.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

Encontré por qué fallaba mi prueba de velocidad, lo arreglé, y la prueba salió perfecta. Catorce productos de catorce, idénticos a los de la corrida lenta, en la cuarta parte del tiempo.

Si me hubiera parado ahí, hoy estaría escribiendo un post triunfal.

Repetí la misma prueba, sin tocar nada. Salieron trece. Faltaba uno y otro era distinto. La tercera vez, cuatro de dieciséis, con errores de datos perdidos.

Mismo programa, misma configuración, mismos datos. Tres resultados.

**Una prueba que sale bien una vez es una anécdota.** Lo que cuenta es la dispersión, y hasta que no la medí no sabía si tenía una mejora o un golpe de suerte. Todavía no lo sé: voy a repetirla unas diez veces antes de decir nada con números.

**Arreglar la causa no es lo mismo que arreglar el problema.** La causa estaba clara (un búfer demasiado pequeño para el ritmo). Con el arreglo, el sistema aguanta cuatro veces la velocidad la mayoría de las veces, no siempre. Con ocho veces, ya no.

**Los resultados distintos entre repeticiones son información.** Algo en el sistema depende del reparto de tiempos, y eso tengo que entenderlo antes de poner un servicio encima.

Y un detalle que me hace desconfiar de mi propia mejora: en el primer volumen de una de las pruebas, mi atajo y la herramienta original dan resultados distintos. En los siguientes coinciden. Sin una referencia externa que diga quién acierta, no puedo presumir nada.

Estado honesto: hay una vía más rápida que probablemente funciona, no la he validado, y no la voy a adoptar hasta que lo esté.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Software #Testing #Rendimiento #Radar #NEXRAD

---
Actualización (2026-11-03): repetido 9 veces con la misma configuración, el 4× dio 2, 0, 2, 2, 0, 1, 2, 2 y 2 productos de unos 14 esperados. No reproduje la corrida buena. Se descarta la vía rápida y se mantiene `play_a2`.
