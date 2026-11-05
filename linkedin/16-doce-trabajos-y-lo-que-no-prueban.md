# Post 16 — Doce trabajos y lo que no prueban

**Hito:** Fase 2 de LAMULA Jobs. Prueba de desgaste del servicio con el software de radar real.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

**Contexto.** Estamos experimentando con el ORPG, el software con el que el Servicio Meteorológico Nacional de EEUU genera productos a partir de los datos crudos de sus radares (NEXRAD). El experimento es un servicio donde alguien elige un evento pasado y lo reproducimos con el programa real. El ORPG se diseñó para arrancar una vez y quedarse funcionando en una estación de radar; nosotros queremos reutilizarlo trabajo tras trabajo. La pregunta es qué se acumula con el uso.

Antes de poner un servicio de larga vida sobre un software pensado para arrancar una vez, hice lo que había aprendido en el post 12: no fiarme de una sola corrida.

**La prueba.** Doce trabajos seguidos por la cola, alternando dos radares distintos (Miami y Houston). Resultado:

- Los doce terminaron bien, con las coordenadas correctas.
- Siete procesos constantes de principio a fin, cero huérfanos, ningún objeto sobrante en el bucket.
- La memoria de cada proceso no tuvo tendencia: entre 5 y 17 MiB, los mismos números en el primer trabajo y en el duodécimo.

**Y una cancelación a mitad de reproducción:** treinta segundos hasta `cancelled`, sin un solo proceso del ORPG vivo y sin schema, usuario ni directorio del trabajo. Esa era la prueba que más me importaba, porque un servicio se rompe más por lo que no limpia que por lo que hace.

**Lo que esto no prueba**, que es la mitad del post:

- Se hizo contra un almacenamiento simulado (moto, un emulador de S3 para pruebas), no contra el de producción. Sus tiempos y sus errores no son los de uno real.
- Cada trabajo era un solo volumen. Un huracán son cientos, y el desgaste con trabajos largos podría ser otro.
- La foto de memoria se toma con el ORPG ya apagado. Demuestra que no se acumula nada *entre* trabajos, no cuánto pesa uno *durante*.
- Un par de procesos (`mrpg` y `nds`) aparecieron veinte segundos después del último trabajo y no sé de dónde vienen. Probablemente inocuos. Probablemente.

**Qué aprender de esto:**

**Para un servicio de larga vida, mide lo que sobra, no solo lo que sale.** Procesos, schemas, usuarios, objetos, directorios y memoria, antes y después. Si cada trabajo termina `ready` pero deja un proceso, el problema aparece el día doscientos.

**Prueba la cancelación como una función de primera clase.** Es el camino con menos tráfico y más estado intermedio.

**Un resultado limpio con sus límites escritos vale más que uno limpio sin ellos.** Los míos están en la documentación, junto a los números, para que quien lea el resultado sepa qué no se probó.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#Fiabilidad #Pruebas #Backend #Radar #Ingeniería
