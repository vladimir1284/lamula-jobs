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

La pregunta de licencia está **resuelta y es mala noticia**: ver
[Licencia del CODE](../referencia/licencia.md). El paquete no trae licencia, pero sí código de
la Universidad de Oklahoma con cláusula no comercial y con "not to be provided or used in any
format", y código de MIT Lincoln Laboratory reproducible solo "by or for the U.S. Government".
Los tres se compilan hoy. Lo que queda son acciones, no dudas:

- **Excluir del build** `src/cpc004/tsk015`, `tsk017`, `tsk019` y `src/cpc023/tsk006`, y
  comprobar que el enlazado del resto aguanta. Cambio en `radar-orpg-dev`, no aquí.
- **Verificar si `src/cpc101/tsk001` es prescindible.** Es ingesta de rejillas de modelo; hay
  que confirmar que DAA, DU3 y DTA no dependen de él antes de cortarlo.
- **Decidir si la imagen sale alguna vez de nuestra infraestructura.** Si el prospecto nunca
  hace `pull` y solo ve productos renderizados en nuestra web, el problema de distribución
  desaparece y solo queda el de uso. Es la vía corta, y la recomendada.
- **Escribir a Michael Istok** (`michael.istok@noaa.gov`) en paralelo, para que conste por
  escrito la postura de la NWS sobre uso comercial y redistribución.
- **Etiquetado de salida**: los productos del demo no pueden presentarse como oficiales del
  NWS, ni usar su nombre o identificadores. Esto toca la interfaz del viewer demo, así que es
  trabajo de F3, no una nota legal al margen.

Nada de esto bloquea F0 ni F1, que corren en nuestra máquina y para nuestro desarrollo. Bloquea
F4, que es cuando entra el primer tercero.

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
