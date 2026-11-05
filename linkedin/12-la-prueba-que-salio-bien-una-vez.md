# Post 12 — La prueba que salió bien una vez

**Hito:** Fase 0 de LAMULA Jobs. Acelerar la reproducción de volúmenes de radar a cuatro veces la velocidad.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

**Contexto.** Seguimos con el experimento de reproducir datos históricos de radar (NEXRAD) por el ORPG, el software que el Servicio Meteorológico Nacional de EEUU usa para generar sus productos. Procesar un volumen tarda unos seis minutos, y en el post anterior intenté acelerarlo con un «radar de mentira» propio que alimenta al ORPG a mayor ritmo, después de ampliar un búfer que perdía datos.

Encontré por qué fallaba, lo arreglé, y la prueba salió perfecta: catorce productos de catorce, idénticos a los de la corrida lenta, en la cuarta parte del tiempo.

Si me hubiera parado ahí, hoy estaría escribiendo un post triunfal.

**Repetí la misma prueba, sin tocar nada.** Salieron trece: faltaba uno y otro era distinto. La tercera vez, cuatro de dieciséis, con errores de datos perdidos. Mismo programa, misma configuración, mismos datos. Tres resultados.

**Qué aprender de esto:**

**Una prueba que sale bien una vez es una anécdota.** Lo que cuenta es la dispersión. Hasta que no la medí no sabía si tenía una mejora o un golpe de suerte. Con una sola corrida no se distinguen.

**Arreglar la causa no es arreglar el problema.** La causa estaba clara (un búfer pequeño para ese ritmo). Con el arreglo el sistema aguantaba cuatro veces la velocidad *a veces*. Si el éxito depende del reparto de tiempos, queda una segunda causa sin encontrar.

**Los resultados distintos entre repeticiones son información.** Algo en el sistema depende de cuándo llegan las cosas, y eso hay que entenderlo antes de poner un servicio encima.

Y un detalle que me hace desconfiar de mi propia mejora: en el primer volumen de una de las pruebas, mi atajo y la herramienta original dan resultados distintos; en los siguientes coinciden. Sin una referencia externa que diga quién acierta, no puedo presumir nada.

*Estado honesto cuando lo escribí:* una vía más rápida que probablemente funciona, sin validar, y que no iba a adoptar hasta validarla.

---
**Actualización (2026-11-03).** Repetido 9 veces con la misma configuración, el modo 4× dio 2, 0, 2, 2, 0, 1, 2, 2 y 2 productos de unos 14 esperados. No reproduje la corrida buena: era suerte. Descartamos la vía rápida y nos quedamos con `play_a2`, la herramienta de reproducción del propio ORPG, que es más lenta pero siempre da el mismo resultado.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Software #Testing #Rendimiento #Radar #NEXRAD
