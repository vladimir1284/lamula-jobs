# Post 07 — El manual decía "interactivo". El código decía otra cosa

**Hito:** Fase 0 de LAMULA Jobs. Lectura del fuente del software del radar antes de montar el contenedor.
**Estado:** borrador — revisar antes de publicar (ver nota al final).

---

Estamos integrando nuestro pipeline con el software real de procesamiento de un radar meteorológico WSR-88D. Es un sistema con décadas encima, pensado para operadores humanos delante de una consola, y nosotros necesitamos que funcione dentro de un trabajo automático sin nadie mirando.

El manual de usuario —y son casi doscientas páginas— describe la herramienta que extrae los productos generados como un programa interactivo: arranca, pregunta el nombre de una lista de productos, pregunta con qué convención quieres nombrar los ficheros, y se queda en un menú. Esa descripción nos tenía anotada una incógnita grande: si no se deja automatizar, el diseño entero cambia.

El paquete, afortunadamente, trae el código fuente. Un rato de lectura ha resuelto esa incógnita y dos más.

**Uno.** El programa tiene una opción, documentada en su propia ayuda pero fácil de pasar por alto, que añade a cada producto un encabezado de comunicaciones de 30 bytes. Y resulta que esa misma opción, como efecto secundario, **suprime la pregunta de la convención de nombres**: si pides el encabezado, el programa decide la convención por su cuenta y no pregunta.

Eso cierra de golpe dos problemas. El de la automatización, y otro que habíamos encontrado días antes por nuestra cuenta: nuestro decodificador necesita ese encabezado —de él saca el identificador del radar— y sin él falla. Resulta que el mismo interruptor resuelve los dos.

**Dos.** La única pregunta que queda, el nombre de la lista de productos, se lee con una función de lectura de entrada estándar completamente corriente. Es decir: un `echo` por delante en la tubería y listo. Y hay otra opción que manda el programa a segundo plano una vez conectado, momento a partir del cual deja de leer el terminal. No hay menú que atender.

El plan B que teníamos anotado —leer directamente el buffer interno del sistema, bastante más trabajo— baja de probabilidad drásticamente.

**Tres**, y esta es la que más cambia el producto. Fui a leer el reproductor de datos, que es el que inyecta las observaciones al sistema, porque teníamos una pregunta abierta: ¿acelerar la reproducción pierde datos?

Lo que encontré:

- Nada en el reproductor descarta datos por ir rápido. La opción de velocidad solo escala la cuenta de cuánto esperar. Si algo se pierde, se pierde después, en la ingesta.
- La opción que creíamos que significaba "a tiempo real" significa, literalmente, "simula también el hueco entre volúmenes". Sin ella, el reloj de referencia se reancla en cada volumen y los tiempos muertos del archivo —que en un radar que estuvo caído media hora son muchos— sencillamente no se esperan.
- Cada espera individual está topada en una fracción de segundo. Hay un comentario junto al tope explicando que sin él se perdían barridos de un volumen concreto. Alguien pasó por ahí antes.
- Y existe un tercer modo, que no estaba en nuestras notas: reproducir a la máxima velocidad **con control de flujo**, gobernado por confirmaciones del propio sistema de procesamiento. Es decir, tan rápido como el receptor admita, no tan rápido como pueda el disco.

Teníamos congelada una decisión de diseño que decía, con buen criterio, "reproducimos a tiempo real y no arriesgamos". Con estos tres modos sobre la mesa, la decisión merece volver a tomarse con datos: si los productos salen idénticos por los tres caminos, un trabajo de demostración pasa de hora y media a minutos, y eso cambia las cuotas, los costes y hasta si hace falta que el demo sea asíncrono.

Ojo: nada de esto está confirmado todavía. Leer el código dice lo que *debería* pasar; solo ejecutarlo dice lo que pasa. La lista de cosas a medir ha cambiado, no se ha acortado.

Lo que sí me parece una conclusión transferible: cuando integras con un sistema que no controlas, el manual te dice cómo se usa y el código te dice cómo funciona. Son dos preguntas distintas. El manual de este describía fielmente la sesión de un operador humano —porque es para lo que se escribió, y lleva décadas siendo correcto—. Lo que no hace, porque no es su trabajo, es contarte qué pasa cuando no hay humano. Para eso hay que ir a mirar.

*Nota: este borrador habla de integrar software de procesamiento de radar de terceros. Revisar con el dueño del producto qué se puede contar públicamente antes de publicarlo.*

#Software #Integracion #Radar #NEXRAD #LeerElCodigo
