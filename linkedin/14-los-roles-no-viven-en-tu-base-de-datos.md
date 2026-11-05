# Post 14 — Los roles no viven en tu base de datos

**Hito:** Fase 2 de LAMULA Jobs. Aislar a cada prospecto con su propio schema y sus propios usuarios.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

Cada trabajo de la demo tiene su schema y dos usuarios de Postgres: uno que escribe y uno que solo lee. Así un visitante no puede ver los datos de otro aunque encuentre la cadena de conexión. Treinta y tres pruebas lo comprueban contra una base real.

Lo que no esperaba: **al borrar la base de datos de pruebas, los usuarios seguían ahí.** En Postgres los roles pertenecen al servidor, no a la base. Cada ejecución de las pruebas dejaba su cola de usuarios, y la siguiente se encontraba con restos de la anterior.

Mi primera solución fue peor que el problema: un limpiador que borraba todos los roles con cierto prefijo. Habría borrado también los de otra base en el mismo servidor, y solo lo paró un error de dependencias. Ahora el limpiador borra únicamente lo que no existía cuando empezó la sesión.

Dos cosas más que salieron de ahí:

- Las contraseñas de cada trabajo no se guardan: se derivan con HMAC de una clave aparte. No hay tabla de secretos que filtrar, y el servicio puede reconstruir una credencial cuando la necesita.
- Un intento de `DROP OWNED BY` falló con «permiso denegado». Resultó innecesario: los roles del trabajo no poseen nada y sus permisos se van con el schema.

**Lo que es global es peligroso de limpiar.** Antes de borrar «lo mío», conviene saber qué existía antes de que yo llegara.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo; hay una consulta de licencia abierta (ver `correspondencia/`).*

#PostgreSQL #Seguridad #Backend #Pruebas #Multitenancy
