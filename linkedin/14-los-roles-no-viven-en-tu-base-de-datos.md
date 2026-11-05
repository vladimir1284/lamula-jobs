# Post 14 — Los roles no viven en tu base de datos

**Hito:** Fase 2 de LAMULA Jobs. Aislar a cada visitante con su propio schema y sus propios usuarios.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

**Contexto.** Estamos experimentando con el ORPG, el software con el que el Servicio Meteorológico Nacional de EEUU genera productos a partir de los datos crudos de sus radares (NEXRAD). El experimento es un servicio donde alguien elige un evento pasado, lo reproducimos con el programa real y lo ve en un visor. Cada visitante lanza su propio *trabajo*, y los resultados de uno no deberían ser visibles para otro.

**El diseño de aislamiento.** Cada trabajo tiene su propio *schema* en PostgreSQL (un espacio de tablas separado dentro de la misma base) y dos usuarios: uno que puede escribir y otro que solo lee, que es el que usa el visor. Así, aunque un visitante encontrara la cadena de conexión de su trabajo, no vería nada de los demás. Hay más de treinta pruebas contra una base real que lo comprueban.

**Lo que no esperaba.** Al borrar la base de datos de pruebas, **los usuarios seguían ahí.** En PostgreSQL los *roles* (usuarios y grupos) pertenecen al servidor entero, no a una base concreta. `DROP DATABASE` no los toca. Cada ejecución de las pruebas dejaba su cola de usuarios, y la siguiente se encontraba con restos de la anterior.

**Mi primera solución fue peor que el problema.** Escribí un limpiador que borraba todos los roles con cierto prefijo. Habría borrado también los de otra base que vive en el mismo servidor, y solo lo paró un error de dependencias que no esperaba. Ahora el limpiador toma una foto de los roles al empezar la sesión y borra únicamente los que no estaban.

Dos cosas más que salieron de ahí:

- **Las contraseñas de cada trabajo no se guardan: se derivan.** Se calculan con HMAC a partir de una clave maestra y el identificador del trabajo. No hay tabla de secretos que filtrar, y el servicio puede reconstruir una credencial cuando la necesita. La clave del usuario que escribe y la del que lee son distintas a propósito, y el proceso que publica datos solo conoce la primera.
- **Un `DROP OWNED BY` falló con «permiso denegado» en PostgreSQL 16.** Resultó innecesario: los roles del trabajo no poseen nada, y sus permisos desaparecen con el schema.

**Qué aprender de esto:**

**Lo que es global es peligroso de limpiar.** Roles, extensiones, tablespaces y otros objetos de servidor sobreviven a la base que los motivó. Antes de borrar «lo mío», averigua qué existía antes de que llegaras, y borra solo la diferencia.

**Las pruebas que crean recursos globales necesitan un teardown que sepa de dónde partieron.** Un prefijo no es una frontera: es una coincidencia de nombres.

**Si puedes derivar un secreto, no lo guardes.** Lo que no se almacena no se filtra, aunque tiene un precio: la clave maestra pasa a ser el único punto que proteger, y rotarla invalida todas las credenciales a la vez.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#PostgreSQL #Seguridad #Backend #Pruebas #Multitenancy
