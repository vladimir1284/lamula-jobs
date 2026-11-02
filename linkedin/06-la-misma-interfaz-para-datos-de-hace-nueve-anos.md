# Post 06 — La misma interfaz, pero con datos de hace nueve años

**Hito:** Fase 0 de LAMULA Jobs. Revisión del visor antes de reutilizarlo para el demo.
**Estado:** listo para publicar.

---

Tenemos un visor de radar meteorológico que funciona bien enseñando lo que está pasando ahora. Para el demo nuevo queremos reutilizarlo tal cual, cambiándole la base de datos por una donde estarán los productos que el cliente ha pedido generar: por ejemplo, un huracán de 2017.

La reutilización parecía gratis. El esquema de datos es el mismo, las consultas son las mismas, el visor ni se entera de dónde sale lo que pinta. Antes de darlo por bueno fui a leer el código del visor buscando dónde supone que los datos son recientes.

Encontré una línea.

El selector de días del visor no lista los días que tienen datos. Lista una ventana de 72 horas anclada a un campo de la tabla de radares que dice cuándo se vio ese radar por última vez. Es una decisión razonable y está documentada: evita depender del reloj del navegador, y para un feed en directo da exactamente lo que se quiere.

El detalle es qué escribe el pipeline en ese campo. Escribe la hora de publicación, no la hora de la observación. En producción son casi la misma cosa, porque un producto se publica tres minutos después de observarse, y nadie ha tenido nunca motivo para distinguirlas.

En un trabajo con datos de 2017 son nueve años de diferencia. El visor abriría, consultaría el radar, vería "visto por última vez: hoy", ofrecería los tres últimos días, y los tres estarían vacíos. El cliente vería una pantalla sin datos y sin ningún error que explicara nada.

Lo bonito es la solución, porque no toca el visor.

Cuando el trabajo termina, lo único que hay que hacer es escribir en ese campo la hora del último volumen observado en vez de la hora de publicación. Una sentencia `UPDATE` de una fila, en una base de datos que es exclusiva de ese trabajo. El visor sigue haciendo exactamente lo que hacía, con el mismo código y la misma consulta, y el selector de días se planta solo en septiembre de 2017.

Y hay un efecto secundario que mejora el producto: el visor tiene un indicador de frescura que dice hace cuánto llegó el último dato. Con la corrección, en lugar de afirmar que un dato de 2017 acaba de llegar, dice su edad real. Que es lo que un cliente mirando un caso histórico debería ver.

Dos lecciones, las dos sobre reutilizar software fuera del contexto para el que se escribió.

La primera: los supuestos tácitos no viven en la lógica, viven en los datos. Nada en el visor dice "esto es para datos en directo". Lo que lo dice es la coincidencia, en producción, entre dos marcas de tiempo que significan cosas distintas. Un campo con dos significados que casi siempre coinciden es una bomba de relojería con el temporizador puesto en "cuando cambies de contexto".

La segunda: encontrarlo fue leer código, no ejecutarlo. Ninguna prueba lo habría cazado, porque todas las pruebas usan datos recientes —por supuesto que sí, son los datos que tenemos—. La pregunta que lo encontró fue explícita y barata: *¿dónde supone este código que los datos son de ahora?* Vale la pena hacérsela a cualquier componente antes de meterlo en un contexto nuevo.

#Software #Reutilizacion #Radar #NEXRAD #Datos
