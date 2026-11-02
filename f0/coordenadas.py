#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["metpy>=1.7.1"]
# ///
"""Comprueba que cada producto de un directorio trae el sitio y las coordenadas esperadas.

Un `change_radar` que no surtió efecto no da ningún error: solo productos con las coordenadas
del sitio anterior. Esta es la comprobación de la regla «las coordenadas se verifican».

    f0/coordenadas.py f0-run/products-T AMX 25.611 -80.413

`siteID` va sin la K (como lo escribe el encabezado WMO), `lat`/`lon` en grados decimales. Los
valores de un sitio salen de `change_radar -l` o de su línea en `change_radar.dat` (milésimas de
grado), nunca de memoria. Verificado con KAMX el 2026-11-02: AMX 25.611 -80.413.

Sale con código 1 si algún producto no coincide. Ignora los ficheros que no son productos.
"""

from __future__ import annotations

import sys
from pathlib import Path

from metpy.io import Level3File

NO_PRODUCTO = ("GSM", "P173_", "RR_")
TOLERANCIA = 0.001  # una milésima de grado: la precisión con que change_radar guarda el sitio


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(__doc__)
        return 2
    carpeta, site, lat, lon = Path(argv[1]), argv[2], float(argv[3]), float(argv[4])
    ok = mal = 0
    for p in sorted(carpeta.iterdir()):
        if not p.is_file() or p.name.startswith(NO_PRODUCTO) or "_GSM" in p.name:
            continue
        try:
            f = Level3File(str(p))
        except Exception as e:  # producto truncado o ilegible: lo dice integridad.py, aquí se cuenta
            print(f"ILEGIBLE  {p.name}  ({type(e).__name__})")
            mal += 1
            continue
        bien = (
            f.siteID == site
            and abs(f.lat - lat) <= TOLERANCIA
            and abs(f.lon - lon) <= TOLERANCIA
        )
        if bien:
            ok += 1
        else:
            mal += 1
            print(f"DISTINTO  {p.name}  site={f.siteID} lat={f.lat} lon={f.lon}")
    print(f"resumen: ok={ok}, mal={mal}")
    return 1 if mal else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
