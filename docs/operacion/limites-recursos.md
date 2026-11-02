# Límites y recursos

El plano demo comparte nodo con producción (D7). Esta página existe para que esa decisión no
se convierta en una sorpresa.

## El riesgo, dicho claro

El ORPG levanta unas 107 tareas y, a tiempo real, sostiene ese ritmo durante toda la duración
del job. En el mismo nodo corren `poller`, `processor`, `wind`, `lightning`, `api`, el viewer,
el Postgres compartido y los respaldos. Si el runner satura el nodo, lo que se degrada es el
demo live, que es lo que ya está enseñándose a clientes.

## Acotaciones

- **Concurrencia 1.** Una réplica del runner. Subir a dos solo con mediciones de F0 que lo
  respalden.
- **Límites y reservas en el servicio**: `limits.cpus`, `limits.memory` para el runner;
  reserva de CPU para `processor`, que es el que no puede llegar tarde.
- **Cola con tope de profundidad.** Llena, `jobs-api` rechaza con un mensaje honesto y una
  estimación de espera.
- **Ventana de ejecución opcional.** Si F0 muestra contención, restringir los jobs a horas de
  poco tráfico es más barato que comprar otro nodo.

## Lo que F0 tiene que medir

| Medida | Para qué |
|---|---|
| RAM pico del ORPG con un volumen real | Fijar `limits.memory` |
| CPU media y pico durante el playback | Fijar `limits.cpus` y decidir si cabe una segunda réplica |
| Retraso del `processor` live durante un job | La prueba de fuego de D7 |
| Duración real de un job de 12 volúmenes | Alimenta la estimación que ve el cliente |
| Tamaño en disco de productos y COGs por volumen | Dimensionar staging y R2 |

Lo que ya se sabe sin contenedor, del lado de la entrada: un job de doce volúmenes de huracán
son **unos 240 MB de descarga** y poco más de una hora de reloj a `-T`; una ventana de seis
horas, más de 1 GB y seis horas de nodo. Detalle por caso en
[Catálogo verificado](../referencia/catalogo-verificado.md).

Si el margen libre del VPS resulta menor que unos dos núcleos, D7 vuelve a la mesa. No es una
decisión irrevocable, es una decisión tomada con los datos de hoy.

## Licencia

Resuelto el 2026-11-01: ver [Licencia del CODE](../referencia/licencia.md). Resumen: el paquete
no trae licencia, pero arrastra código de terceros con cláusula no comercial que hoy se compila.
Tanto ofrecerlo como servicio comercial como distribuir la imagen están prohibidos **tal como
se compila hoy**; se subsana excluyendo cinco directorios del build. Las acciones concretas
están en [Pendientes](../alcance/pendientes.md).
