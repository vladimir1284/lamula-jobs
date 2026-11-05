# Post 17 — El resultado que llega por partes

**Hito:** Fase 2 de LAMULA Jobs, requisito de la Fase 3. Publicar mientras el trabajo corre.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

**Contexto.** Estamos experimentando con el ORPG, el software con el que el Servicio Meteorológico Nacional de EEUU genera productos a partir de los datos crudos de sus radares. El experimento: alguien elige un evento pasado y lo reproducimos con el programa real. Un trabajo de huracán dura más de una hora.

**El problema.** Mi primera versión publicaba todo al final. Funcionaba, pero la promesa era otra: abrir el enlace *mientras* corre y ver los mapas apareciendo. Una hora de pantalla vacía no es una demo.

**El cambio.** El programa que produce los ficheros los suelta a medida que están completos, y el worker los publica por lotes cada 15 segundos. La parte delicada: un fichero a medio escribir, decodificado, falla en silencio (ya me pasó, post 8). Así que un producto solo sale si su longitud real coincide con la declarada en su cabecera **y** su tamaño no cambió entre dos sondeos.

**Medido, con un trabajo real de 3 volúmenes:**

- El primer producto aparece a los 80 segundos.
- El contador de productos crece en 8 pasos distintos con el trabajo aún en marcha (1, 3, 4, 5, 9, 10, 11, 15).
- Terminó con 15, sin restos.

**Lo que no prueba:** un solo trabajo, tres volúmenes, un radar. Los productos salen en ráfagas, no a ritmo constante, y no comparé uno a uno con la versión de publicar al final.

**Qué aprender de esto:**

**Si la promesa es "en vivo", mídela con el reloj, no con el estado final.** Un resultado correcto que llega tarde no cumple.

**Publicar a medias exige una definición de "entero" que no dependa de la suerte.** Dos condiciones baratas valen más que una espera larga.

*Nota: habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Radar #Backend #Ingeniería #Pruebas #TiempoReal
