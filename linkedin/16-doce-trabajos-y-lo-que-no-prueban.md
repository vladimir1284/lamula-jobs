# Post 16 — Doce trabajos y lo que no prueban

**Hito:** Fase 2 de LAMULA Jobs. Prueba de desgaste del servicio con el software de radar real.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

Antes de poner un servicio de larga vida sobre un software de radar pensado para arrancar una vez, hice lo que había aprendido en el post 12: no fiarme de una sola corrida.

Doce trabajos seguidos por la cola, alternando dos radares distintos (Miami y Houston). Resultado: los doce terminaron bien, con las coordenadas correctas, siete procesos constantes de principio a fin, cero huérfanos y ningún objeto sobrante en el bucket. La memoria residual de cada proceso no tuvo tendencia: entre 5 y 17 MiB, los mismos números al primer trabajo y al duodécimo.

Y una cancelación a mitad de reproducción: treinta segundos hasta `cancelled`, sin un solo proceso del radar vivo y sin schema, usuario ni directorio. Esa es la prueba que me importaba más, porque un servicio se rompe por lo que no limpia, no por lo que hace.

Ahora, lo que esto **no** prueba, que es la mitad del post:

- Se hizo contra un almacenamiento simulado, no contra el de producción.
- Cada trabajo era un solo volumen. Un evento de horas tiene muchos.
- La foto de memoria se toma con el software ya apagado. Demuestra que no se acumula nada *entre* trabajos, no cuánto pesa uno *durante*.
- Un par de procesos aparecieron veinte segundos después del último trabajo y no sé de dónde vienen. Probablemente inocuos. Probablemente.

**Un resultado limpio con sus límites escritos vale más que uno limpio sin ellos.** Los límites ya están en la documentación, junto a los números.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Fiabilidad #Pruebas #Backend #Radar #Ingeniería
