# Borrador — consulta de licencia a Michael Istok

- **Para:** Michael Istok, Radar Product Improvement Manager, NOAA/NWS — michael.istok@noaa.gov
- **Copia sugerida:** Brian Klein — brian.klein@noaa.gov (autor de las instrucciones de instalación; las preguntas 3 y 4 son suyas)
- **Fecha del borrador:** 2026-11-02
- **Estado:** pendiente de revisión del dueño del producto antes de enviar.

Contexto y hallazgos en [Licencia del CODE](../docs/referencia/licencia.md). El borrador separa a
propósito tres cosas que son distintas: lo que la NWS permite, lo que permite la Universidad de
Oklahoma, y lo que pasa cuando el software se instala en la máquina de un cliente.

---

**Subject:** CODE Build 24.0 — request for licensing clarification (third-party copyright headers)

Dear Mr. Istok,

Thank you again for sending us the Public Edition of CODE (CODERPG Build
24.020260715033855). We have it building and running in a container for our own development, and
we would like to clarify what we are permitted to do with it before we go any further.

**What we are building.** We are a small company that provides installation, configuration and
support services for weather radar processing systems. Our own software stack is open source. We
are preparing a free public web demo: a visitor picks an archived storm from the public NEXRAD
Level II archive on AWS, we replay those volumes into an RPG built from CODE, and we render the
resulting Level III products in a browser. The demo is free, requires no payment, and is open to
anyone. Its purpose is to show prospective customers what the processing chain can do, so while
the demo itself is free, we will not pretend it has no commercial motive.

**What we found in the package.** The package does not contain a LICENSE, COPYING or NOTICE
file. It does contain third-party copyright headers inside source that is compiled by the default
build:

1. `src/cpc004/tsk015` and `src/cpc004/tsk017` (QVP and Range-Defined QVP) — "Copyright 2023
   Board of Regents of the University of Oklahoma ... subject to the CC BY-NC-SA 4.0 Creative
   Commons License". CC BY-NC-SA excludes use primarily intended for commercial advantage.
2. `src/cpc004/tsk019` (QZdrCal) and `src/cpc023/tsk006` (ARML) — "(c) Copyright 2022, Board of
   Regents of the University of Oklahoma. All rights reserved. Not to be provided or used in any
   format without the express written permission of the University of Oklahoma." (for example
   `compute_qzdrcal.h`, lines 24-27). This one restricts *use*, not only distribution, and makes
   no distinction between commercial and non-commercial.
3. `src/cpc101/tsk001` (model grid ingest) — "(c) Copyright, 2022 Massachusetts Institute of
   Technology. This material may be reproduced by or for the U.S. Government pursuant to the
   copyright license under the clause at 252.227-7013 (Jun. 1995)."

All of these are reached by the default build: `src/makefile` lists `cpc004`, `cpc023` and
`cpc101` in `SUBDIRS`, and `src/cpc004/makefile` lists `tsk015 tsk017 tsk019`.

We have also read the Terms and Conditions for the Public Edition
(https://www.weather.gov/code88d/code_disclaimer). We read it as a disclaimer of warranty and
support rather than a licence grant: it neither permits nor forbids commercial use, so it does
not answer the questions above.

**Our questions.** We would be grateful for your position on the following. Where the answer is
not NWS's to give, a pointer to the right office would help us just as much.

1. Does the NWS consider the Public Edition usable by a private company to operate a free public
   demonstration of this kind?
2. Regarding the University of Oklahoma files: does the NWS hold a permission from OU that
   extends to recipients of the package, or should we read those headers as applying to us
   directly? If the latter, who at OU should we approach — the Office of Technology
   Commercialization, or the named author?
3. Is `src/cpc101/tsk001` required for the digital accumulation products (DAA, DU3, DTA), or can
   it be excluded from the build without affecting them? We do not need model grid ingest.
4. If we exclude `cpc004/tsk015`, `tsk017`, `tsk019`, `cpc023/tsk006` and possibly
   `cpc101/tsk001` from `SUBDIRS`, is that an acceptable and supported way to use the package? Is
   there a known-clean build configuration we should use instead? We are holding off on any build
   change until we hear from you.
5. On redistribution, which is the point that matters most to us commercially. We do not
   republish the package or its binaries: the demo runs only on our own infrastructure and
   visitors never download anything. But part of our business is installing and configuring this
   software on a customer's own hardware, and we are aware that this means the package reaches
   the customer's machine. We would rather get this right from the start. Would you prefer that
   each customer requests the package from you directly, under their own name, and that our role
   be limited to installation, configuration and support of software they obtained themselves?
6. On attribution, we intend to label all demo output as unofficial, to avoid the NWS and NOAA
   names and visual identifiers, and to make no claim of endorsement or affiliation. Please tell
   us if anything further is required.

We are happy to send a short description of our architecture if that would help, and we will
restrict the package to internal development until we have your answer.

Thank you for your time.

Best regards,

Vladimir Rodríguez
Ladetec
vladimir.rodriguez@pinkzebrahome.com
