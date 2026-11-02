# Post 01 — Los treinta bytes que no venían en el contrato

**Hito:** Fase 0 de LAMULA Jobs (demo bajo demanda con ORPG real). Hallazgo previo a montar el contenedor.
**Estado:** listo para publicar.

---

Estamos montando un demo que procesa radar meteorológico de verdad: el cliente elige una secuencia de observaciones crudas —un huracán del pasado, por ejemplo—, un ORPG real las convierte en productos, y esos productos entran por nuestro pipeline hasta el visor. La cadena entera, no un trozo.

El plan era empezar por una espiga manual: un contenedor, un volumen, y mirar qué sale. Antes de llegar ahí apareció algo que conviene contar, porque es el tipo de fallo que normalmente se descubre a las dos de la mañana del día de la demostración.

Nuestro pipeline lleva meses decodificando productos Level III sin una queja. Los baja de un bucket público y los convierte en rásters calibrados. Funciona. La pregunta era si tragaría igual los productos que escribe nuestro propio ORPG, que son el mismo formato definido en el mismo documento de interfaz.

Spoiler: no. Y no por el formato.

Los ficheros del bucket público empiezan con treinta bytes de texto plano:

```
SDUS52 KMFL 010000\r\r\nN0BAMX\r\r\n
```

Es un encabezado de comunicaciones. No lo pone el radar: lo pone la distribución del Servicio Meteorológico Nacional al meter el producto en su red. Dice de qué circuito viene, de qué oficina, a qué hora, y —en la segunda línea— qué producto es y de qué radar.

La librería que usamos para decodificar busca ese encabezado, y si lo encuentra, guarda esos tres últimos caracteres como identificador del radar. Si no lo encuentra, no guarda nada. Ni cadena vacía, ni valor por defecto: el atributo sencillamente no existe.

Nuestro decodificador lee ese atributo en tres sitios. Y ese identificador de tres letras es la clave primaria de la tabla de radares, la referencia de las tablas de rásters, fenómenos y perfiles de viento, y el primer segmento de la ruta en el almacén de objetos.

Así que hicimos el experimento más barato posible: coger un producto real del bucket, quitarle los treinta bytes, y decodificar los dos.

Resultado: el código del producto, la latitud, la longitud y los datos salen idénticos. Lo único que cambia es que el segundo revienta con un `AttributeError` antes de escribir nada.

Un enlace de salida del ORPG —el que simula un usuario de la red— entrega el producto tal cual, sin encabezado de comunicaciones, porque ese encabezado pertenece a la red que lo distribuye, no al radar que lo genera. Es decir: tenemos buenas razones para esperar que nuestro ORPG nos entregue justo el caso que rompe.

Lo interesante no es el error. Es dónde estaba escondido.

Durante meses el productor y el consumidor de esos ficheros fueron el mismo bucket, así que el contrato entre ambos nunca hizo falta escribirlo. Funcionaba por coincidencia de origen. En el momento en que metemos un segundo productor —nuestro propio ORPG—, el contrato tácito aparece de golpe, y resulta que incluía treinta bytes que no son del formato de datos, sino de la red por la que ese formato viajaba.

La tentación evidente es fabricar el encabezado: son treinta bytes, se generan en una línea. La descartamos, y por un motivo que no es técnico. Ese encabezado identifica tráfico oficial del servicio meteorológico. Estamparlo en productos nuestros es presentarlos como lo que no son, justo en un demo cuya primera regla es que su salida no puede confundirse con un producto oficial. El arreglo correcto es el aburrido: que el decodificador acepte un identificador explícito cuando el encabezado no está. El trabajo que ejecuta el job sabe perfectamente de qué radar es; acaba de configurarlo él mismo.

Coste de encontrarlo: una descarga de 188 KB y veinte líneas de script. Coste de no encontrarlo: la espiga completa montada, el contenedor corriendo, los volúmenes descargados, y un `AttributeError` al final de la cadena sin ninguna pista de por qué el mismo decodificador que lleva meses funcionando de pronto no funciona.

La costumbre que lo hizo posible no tiene mérito ninguno: antes de integrar dos cosas que nunca se han hablado, escribe qué espera cada una. Normalmente descubres que una de las dos esperaba algo que nadie había dicho en voz alta.

#Radar #NEXRAD #Python #IngenieriaDeDatos #Interoperabilidad
