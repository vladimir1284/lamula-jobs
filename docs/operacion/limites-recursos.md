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

## Lo que ya está medido sin contenedor

**Entrada.** Un job de doce volúmenes de huracán son **unos 240-300 MB de descarga** y entre 80
y 88 minutos de reloj a `-T` (medido en F0: ~78 min con `-m`, D6). Detalle por caso en
[Catálogo verificado](../referencia/catalogo-verificado.md).

**Salida y procesamiento.** Medido el 2026-11-02 pasando los diez productos reales de un
volumen por `l3proc process`, en una máquina de dos núcleos aarch64 —no el nodo del Swarm, así
que los tiempos valen como orden de magnitud y como reparto entre productos, no como cifra
operativa—:

| Volumen | Productos crudos | COGs resultantes | CPU de decodificación |
|---|---|---|---|
| KTBW en el pico de Ian | 0,86 MB | **4,41 MB** (7 rásters) | 5,6 s |
| KAMX en un día tranquilo | 0,47 MB | 2,30 MB | 4,2 s |

Reparto dentro del volumen de huracán: N0B 2,5 s y 1,46 MB, N0G 0,9 s y 0,92 MB, DTA 0,7 s y
0,83 MB, DU3 0,6 s, DAA 0,5 s, EET y DVL por debajo de 0,2 s y 54 KB cada uno. El importador
de MetPy y Rasterio cuesta 2,4 s, pero se paga una vez: el runner usa `l3proc watch`, no una
invocación por fichero.

Tres conclusiones:

1. **El procesamiento no es el cuello de botella.** Un job de doce volúmenes son unos 70
   segundos de CPU de pipeline contra 85 minutos de reproducción del ORPG. Lo que hay que
   vigilar en D7 es el ORPG, no `l3proc`.
2. **La huella en R2 es pequeña**: unos 53 MB de COGs por job de doce volúmenes de huracán. El
   staging de Level II pesa cinco veces más que el resultado.
3. Queda por medir lo que sí necesita contenedor: la RAM y la CPU del ORPG durante el playback,
   y el retraso que le mete al `processor` del demo live.

Si el margen libre del VPS resulta menor que unos dos núcleos, D7 vuelve a la mesa. No es una
decisión irrevocable, es una decisión tomada con los datos de hoy.

## Licencia

Resuelto el 2026-11-01: ver [Licencia del CODE](../referencia/licencia.md). Resumen: el paquete
no trae licencia, pero arrastra código de terceros con cláusula no comercial que hoy se compila.
Tanto ofrecerlo como servicio comercial como distribuir la imagen están prohibidos **tal como
se compila hoy**; se subsana excluyendo cinco directorios del build. Las acciones concretas
están en [Pendientes](../alcance/pendientes.md).
