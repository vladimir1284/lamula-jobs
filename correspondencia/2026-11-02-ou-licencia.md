# Borrador — consulta de licencia a la Universidad de Oklahoma

- **Para:** Office of Technology Commercialization, University of Oklahoma —
  **dirección por confirmar** en https://ou.edu/otc antes de enviar. No la inventes.
- **Copia sugerida:** John M. Krause (CIWRO/NSSL), autor nombrado en las cabeceras de QVP y
  QZdrCal. Dirección también por confirmar.
- **Fecha del borrador:** 2026-11-02
- **Estado:** pendiente de revisión del dueño del producto antes de enviar.

Va en paralelo con [la consulta a la NWS](2026-11-02-istok-licencia.md), no después: la NWS no
puede responder por OU, y esperar su respuesta para escribir esta cuesta semanas. Las dos
preguntas son independientes.

La pregunta 4 es la que esperamos que resuelva el asunto. Las otras están para que, si OU
contesta corto, la respuesta siga sirviendo.

---

**Subject:** Licensing of University of Oklahoma components in the NWS CODE Public Edition
(QVP, Range-Defined QVP, QZdrCal, ARML)

Dear Sir or Madam,

I am writing to ask for clarification on the terms under which we may use several source files
that bear a University of Oklahoma copyright notice.

**How we obtained the code.** We received the Public Edition of the NWS Common Operations and
Development Environment (CODE) for the WSR-88D Open Radar Product Generator, build
`CODERPG Build 24.020260715033855`, directly from NOAA/NWS on request. The package is
distributed by the National Weather Service at https://www.weather.gov/code88d/ and is sent by
email to named recipients. It contains no LICENSE, COPYING or NOTICE file.

**The files in question.** Reviewing the source, we found two different University of Oklahoma
notices, in code that the default build compiles:

1. In `src/cpc004/tsk015` (Quasi-Vertical Profile) and `src/cpc004/tsk017` (Range-Defined QVP):

   > Copyright 2023 Board of Regents of the University of Oklahoma. ... are subject to the
   > CC BY-NC-SA 4.0 Creative Commons License

2. In `src/cpc004/tsk019` (QZdrCal) and `src/cpc023/tsk006` (ARML), for example in
   `compute_qzdrcal.h`, lines 24-27:

   > (c) Copyright 2022, Board of Regents of the University of Oklahoma. All rights reserved.
   > Not to be provided or used in any format without the express written permission of the
   > University of Oklahoma.

Both notices are reached by the default build: `src/makefile` lists `cpc004` and `cpc023` in
`SUBDIRS`, and `src/cpc004/makefile` lists `tsk015 tsk017 tsk019`. Building the package as
distributed therefore compiles all of them.

**What we want to do.** We are a small company that provides installation, configuration and
support services for weather radar processing systems; our own software is open source. We
intend to run an RPG built from CODE on our own servers to power a free public web
demonstration: a visitor selects an archived storm from the public NEXRAD Level II archive, we
replay it, and we display the resulting Level III products in a browser. No payment and no
account are required to use it. We also expect to install and configure CODE-derived systems on
customers' own hardware as a paid service, in which case the software reaches the customer's
machine.

We should be plain about one point rather than let it be inferred: although the demonstration
itself is free of charge, its purpose is to win business for our services. We are therefore not
claiming that it is non-commercial use under CC BY-NC-SA, and we would rather ask than assume.

**Our questions.**

1. Do these notices apply to us as a recipient of the NWS Public Edition, or has the University
   granted the National Weather Service a licence that extends to those it distributes the
   package to? The NWS terms page is a disclaimer of warranty and does not address this.
2. For the CC BY-NC-SA 4.0 files: do you consider a free, publicly accessible demonstration
   operated by a company that sells related services to fall outside the NonCommercial
   limitation, or inside it? We assume inside, and so unavailable to us without a separate
   licence, but we would like that confirmed either way.
3. For the "not to be provided or used in any format" files: is the University willing to grant
   written permission for use, and if so under what conditions? This notice restricts use and
   not only distribution, and it makes no distinction between commercial and non-commercial, so
   we read it as covering any use of those files by us at all.
4. **The question we most need answered.** If we exclude `src/cpc004/tsk015`,
   `src/cpc004/tsk017`, `src/cpc004/tsk019` and `src/cpc023/tsk006` from the build, so that no
   University of Oklahoma code is compiled, executed or distributed by us in any form, does the
   University have any remaining objection to our use of the rest of the package? None of the
   products our processing chain consumes originate in those directories.
5. If a commercial licence for any of these components is available, we would be glad to hear
   what it would involve. We would rather pay for a licence than work around the code if the
   terms are proportionate to the size of our business.

We have made no modification to the build so far and we are not using the package for anything
beyond internal development while this is unresolved. We have put the same questions about the
package as a whole to the NWS contact for CODE.

Thank you for your time.

Best regards,

Vladimir Rodríguez
Ladetec
vladimir.rodriguez@pinkzebrahome.com
