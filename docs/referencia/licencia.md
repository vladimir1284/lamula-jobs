# Licencia del CODE: qué se puede y qué no

Investigado el 2026-11-01 sobre el paquete `CODERPG Build 24.020260715033855`. Las citas de
código están verificadas directamente contra el tarball de fuentes; las de la NWS vienen de sus
páginas públicas y llevan URL.

## El hallazgo en una línea

**El paquete no trae ninguna licencia.** Ni `LICENSE`, ni `COPYING`, ni `NOTICE` — 6.494
ficheros revisados. Lo que sí trae son **cabeceras de copyright de terceros dentro de código
que sí se compila**, y algunas son muy restrictivas.

## Lo que bloquea

### Universidad de Oklahoma, cláusula no comercial

En `src/cpc004/tsk015`, `tsk017` y `tsk019` (ocho ficheros):

```
// Copyright 2023 Board of Regents of the University of Oklahoma. ... are subject to the
// CC BY-NC-SA 4.0 Creative Commons License
```

CC BY-NC-SA prohíbe el uso dirigido principalmente a ventaja comercial. Un demo de ventas es
exactamente eso.

### Universidad de Oklahoma, "ni usar ni proveer"

En los mismos directorios, seis ficheros más llevan algo peor —fíjate en **used**, no solo
"distributed":

```
//(c) Copyright 2022, Board of Regents of the University of Oklahoma.
//All rights reserved. Not to be provided or used in any format without
//the express written permission of the University of Oklahoma.
```

(`src/cpc004/tsk019/compute_qzdrcal.h`, líneas 24-27.)

### MIT Lincoln Laboratory, cláusula DFARS

En `src/cpc101/tsk001` (ocho ficheros):

```
 *   (c) Copyright, 2022 Massachusetts Institute of Technology.
 *       This material may be reproduced by or for the
 *       U.S. Government pursuant to the copyright license
 *       under the clause at 252.227-7013 (Jun. 1995).
```

El permiso de reproducción es "by or for the U.S. Government". Una empresa privada
reproduciéndolo para su demo comercial no encaja ahí.

### Y se compilan

Verificado en los makefiles: `src/makefile` lista `cpc004`, `cpc023` y `cpc101` en `SUBDIRS`;
`src/cpc004/makefile` lista `tsk015 tsk017 tsk019`. No son opcionales en tiempo de compilación,
aunque algunos sí lo sean en tiempo de ejecución.

## Lo que la NWS sí dice, y no estorba

La página [Terms and Conditions for the Public Edition of
CODE](https://www.weather.gov/code88d/code_disclaimer) es un descargo de responsabilidad, no
una licencia: software "as is", sin soporte, sin garantía, y el aviso de que los componentes
propietarios del ORPG no van en el paquete público. **No concede derechos ni prohíbe el uso
comercial.** La restricción comercial viene solo de OU.

No hay control de exportación declarado en ninguna parte del material, ni ITAR ni EAR. Tampoco
hay declaración de dominio público: el 17 U.S.C. § 105 no salva nada aquí, porque el paquete
contiene obra de OU, MIT/LL, Northrop Grumman y varias librerías JavaScript de terceros.

## Veredicto

| Pregunta | Veredicto |
|---|---|
| Ejecutarlo como servicio para un demo comercial | **Prohibido tal como se compila hoy.** Subsanable. |
| Distribuir la imagen con los binarios, aunque sea en GHCR privado | **Prohibido tal como está.** Tres cláusulas independientes lo impiden. |

## Mitigación

Excluir del build los directorios contaminados. Son funcionalidad accesoria, no el núcleo:

| Directorio | Qué es | Licencia | ¿Prescindible? |
|---|---|---|---|
| `src/cpc004/tsk015` | QVP | CC BY-NC-SA + todos los derechos reservados | Sí |
| `src/cpc004/tsk017` | Range-Defined QVP | CC BY-NC-SA | Sí |
| `src/cpc004/tsk019` | QZdrCal | todos los derechos reservados | Sí |
| `src/cpc023/tsk006` | ARML, capa de fusión | todos los derechos reservados | Sí: su propio `README.txt` lo da como extensión que hay que activar a mano |
| `src/cpc101/tsk001` | Ingesta de rejillas de modelo | MIT/LL DFARS | **Por verificar.** HCA y QPE podrían necesitarlo. |

Los tres primeros salen editando `SUBDIRS` en `src/cpc004/makefile`; los otros dos en
`src/makefile`. Hay que comprobar que el enlazado del resto no se rompe.

Ninguno de los diez productos que consume el pipeline (N0B, N0G, EET, DVL, DAA, DU3, DTA, NMD,
NST, NVW) sale de esos directorios. El que hay que mirar con lupa es `cpc101/tsk001`, por si
DAA/DU3/DTA dependen de las rejillas de modelo.

## La vía corta

Si la imagen **nunca sale de nuestra infraestructura** —el prospecto ve productos renderizados
en nuestra web y jamás hace `pull`— el problema de distribución desaparece y solo queda el de
uso, que se resuelve excluyendo el código de OU. Eso reduce el riesgo a casi nada sin esperar
respuesta de nadie.

## Condiciones que aplican igualmente

Del [descargo general de la NWS](https://www.weather.gov/disclaimer):

1. No presentar los productos como oficiales del NWS. Etiquetar la salida como no oficial.
2. No usar el nombre "National Weather Service" ni identificadores visuales de NOAA/NWS: están
   protegidos como marca.
3. No implicar respaldo ni afiliación con NOAA/NWS.
4. Si la obra resultante consiste predominantemente en material del NWS, incluir el aviso del
   17 U.S.C. § 403.
5. Conservar los avisos MIT de las librerías JavaScript de terceros si se usa la interfaz web
   `cpc001/tsk050`.

## Riesgo que no se despeja leyendo

La NWS distribuye públicamente código marcado "Not to be provided or used in any format without
the express written permission of the University of Oklahoma". O la NWS tiene un permiso que no
se transfiere a quien recibe el paquete, o es un descuido de empaquetado. En cualquiera de los
dos casos, ese permiso no lo tenemos nosotros. Solo lo resuelve OU por escrito.

## A quién escribir

| Para qué | Quién |
|---|---|
| Uso comercial y redistribución del CODE | Michael Istok, Radar Product Improvement Manager, NOAA/NWS — `michael.istok@noaa.gov`, contacto oficial declarado para el CODE |
| Si `cpc101/tsk001` es prescindible; si hay un build limpio | Brian Klein, ITegrity Inc. — `brian.klein@noaa.gov`, autor de las instrucciones de instalación |
| Uso comercial del código QVP/QZdrCal/ARML, si se decide no excluirlo | Office of Technology Commercialization de la Universidad de Oklahoma, y John M. Krause (CIWRO/NSSL), autor nombrado en las cabeceras |
| Solo si `cpc101/tsk001` resulta imprescindible | MIT Lincoln Laboratory, Technology Transfer |

Nota de contexto: el paquete no se descarga anónimamente. Se pide por correo a Istok y llega
por Kiteworks. Es distribución nominal y controlada, lo que refuerza que republicar sus
binarios no entra en el modelo previsto.
