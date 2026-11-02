# Contexto y alcance

## Qué es

Un servicio que acepta **trabajos (jobs)**. Un job es una lista ordenada de volúmenes Level II
de un mismo radar. El servicio los reproduce contra un ORPG real, captura los productos Level
III que el ORPG genera, los procesa con el pipeline existente y los publica en un espacio
aislado que el cliente abre con un enlace.

## Qué no es

- **No es un procesador en tiempo real.** Eso ya existe: `nexrad-l3-pipeline` ingiere el feed
  público de Unidata cada 60 s. Aquí se reproduce historia a petición.
- **No genera productos por su cuenta.** Todos los productos salen del ORPG. Nada de
  algoritmos propios.
- **No es un visor nuevo.** Reutiliza `lamula-webviewer` tal cual, apuntado a otros almacenes.

## Relación con los demás repos

| Repo | Papel aquí |
|---|---|
| `radar-orpg-dev` | Aporta la imagen `ghcr.io/vladimir1284/orpg:b24` (privada) y el trazo de instalación. La imagen del runner se construye **sobre** ella. |
| `nexrad-l3-pipeline` | Aporta el decodificador y el publicador (`l3proc watch`), el schema Postgres y el contrato con el viewer. Se usa **sin tocar el contrato**. |
| `lamula-webviewer` | Aporta el visor. Se despliega una segunda instancia apuntada a los almacenes demo. |
| `lamula-process` | Aporta el conocimiento del bucket Level II de AWS (`src/lib/aws-explorer/`) y el catálogo de sitios `known-sites.json`. |
| `lamula-rcp` | Futuro: archiva observaciones propias como Level II y emula un RDA. Es la fuente de entrada número dos de este servicio. |

## El contrato de entrada, y por qué importa

La entrada de un job es **una lista ordenada de volúmenes Level II en staging**. No es "una
selección de AWS" ni "una subida de ficheros". El origen es un detalle de quien prepara el
staging.

Esto no es purismo. La primera fuente es el catálogo público de AWS. La segunda, ya
comprometida, es la herramienta con la que el cliente convierte sus propias observaciones a
Level II. Si el runner supiera de dónde salen los ficheros, la segunda fuente obligaría a
reescribirlo.

## Para quién

Prospectos que evalúan la suite. El acceso es por token que entregamos a mano tras una
solicitud por correo; no hay registro público. Ver [Acceso y cuotas](../operacion/acceso-y-cuotas.md).
