# Pendientes

Huecos abiertos, ordenados por lo que bloquean.

## Bloqueantes de F0

- **Automatizar `nbtcp`.** Interactivo por diseño. Hay que comprobar que un wrapper por stdin
  basta, o pasar al plan B (leer el product LB del ORPG).
- **Aislamiento entre jobs.** Comprobar que `mrpg -p startup` no deja rastro del job anterior.
  Un producto filtrado es un fallo silencioso.
- **Decodificación de la salida de `nbtcp`.** El pipeline decodifica ficheros del bucket de
  Unidata, que no traen cabecera WMO. Hay que confirmar que MetPy traga igual lo que escribe
  `nbtcp`.
- **Velocidad segura de reproducción.** `-T` es lo documentado; falta saber si `-x` mayor que 1
  pierde radiales.

## Bloqueantes de la apertura a terceros

- **Licencia del CODE Public Edition**: ¿permite ofrecerlo como servicio a terceros? Pendiente
  legal, no técnico. Ver [Límites y recursos](../operacion/limites-recursos.md).

## Decisiones que faltan

- Dominio del viewer demo y del hostname del bucket.
- Texto y campos exactos del formulario de solicitud de acceso.
- Umbral de huecos aceptable entre volúmenes consecutivos de un job.
- Qué hacer cuando el cliente elige un rango con un cambio de VCP en medio (clear-air a
  precipitación): ¿se permite, se avisa, se corta?
- Si el enlace de resultado caduca a la vez que el job o sobrevive un tiempo en solo lectura.

## Cambios necesarios en repos ajenos

| Repo | Cambio | Tamaño |
|---|---|---|
| `nexrad-l3-pipeline` | `R2_KEY_PREFIX` opcional en `ingest/storage/keys.py` | pequeño, aditivo |
| `lamula-webviewer` | Credenciales por token de job, línea de tiempo en la ventana del job, pantalla de estado, ocultar viento y rayos en jobs históricos | mediano, aditivo |
| `lamula-process` | Ninguno. De ahí solo se porta conocimiento y datos. | — |

## Deuda consciente

- Un job es de un solo radar: sin mosaico.
- Sin viento ni rayos históricos.
- Sin productos 59, 61 y 62 pese a que el ORPG los genera.
