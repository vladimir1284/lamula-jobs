#!/usr/bin/env python3
"""Compara dos directorios de salidas de `l3proc` (COGs y JSON) fichero a fichero.

    f0/comparar_salidas.py viejo/cogs nuevo/cogs

COG: mismos píxeles, misma geotransformación y mismo CRS. JSON: mismo contenido tras cargarlo.
Necesita rasterio y numpy: se corre con el Python de la imagen `job-runner`
(`/opt/pipeline/.venv/bin/python`). Sale con código 1 si algo difiere o falta.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    a, b = Path(argv[1]), Path(argv[2])
    na, nb = {p.name for p in a.iterdir()}, {p.name for p in b.iterdir()}
    mal = [f"solo en {a}: {n}" for n in sorted(na - nb)] + [f"solo en {b}: {n}" for n in sorted(nb - na)]
    iguales = 0
    for n in sorted(na & nb):
        if n.endswith(".tif"):
            with rasterio.open(a / n) as x, rasterio.open(b / n) as y:
                ok = (x.transform == y.transform and x.crs == y.crs and x.shape == y.shape
                      and np.array_equal(x.read(), y.read()) and x.tags() == y.tags())
        elif n.endswith(".json"):
            ok = json.loads((a / n).read_text()) == json.loads((b / n).read_text())
        else:
            continue
        iguales += ok
        if not ok:
            mal.append(f"DISTINTO {n}")
    print("\n".join(mal[:40]))
    print(f"iguales={iguales} distintos_o_ausentes={len(mal)}")
    return 1 if mal else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
