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

Si el margen libre del VPS resulta menor que unos dos núcleos, D7 vuelve a la mesa. No es una
decisión irrevocable, es una decisión tomada con los datos de hoy.

## Licencia

La imagen del ORPG es redistribución restringida; por eso el paquete de GHCR es privado.
Ofrecerla **como servicio** a terceros no es lo mismo que redistribuirla, pero tampoco es
obviamente lo mismo que usarla en desarrollo. Hay que leer la licencia del CODE Public Edition
antes de abrir esto a prospectos. Es un pendiente bloqueante de tipo legal, no técnico.
