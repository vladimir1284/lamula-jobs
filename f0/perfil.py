#!/usr/bin/env python3
"""Resume el CSV de `f0/perfil.sh`: CPU por proceso del ORPG durante una reproducción.

    f0/perfil.py perfil-m.csv

El CSV trae `tiempo_epoch,proceso,ticks_acumulados`. Los ticks son de 1/100 s (CLK_TCK); un
proceso que se reinicia puede bajar su contador, así que solo se suman los incrementos
positivos. Para cada proceso saca los segundos de CPU totales y su parte, y cuántos núcleos
usó de media. Como el ORPG usa 4 núcleos en esta máquina, si la suma de CPU es mucho menor que
`4 × duración` el cuello de botella no es el cómputo sino la espera.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict

CLK_TCK = 100


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    last: dict[str, int] = {}
    total: dict[str, float] = defaultdict(float)
    t0 = t1 = None
    with open(argv[1]) as fh:
        for row in csv.reader(fh):
            if len(row) != 3:
                continue
            t, name, ticks = int(row[0]), row[1], int(row[2])
            t0 = t if t0 is None else t0
            t1 = t
            if name in last and ticks > last[name]:
                total[name] += (ticks - last[name]) / CLK_TCK
            last[name] = ticks
    if t0 is None or t1 == t0:
        print("sin datos")
        return 1
    span = t1 - t0
    cpu = sum(total.values())
    print(f"ventana {span} s, CPU total {cpu:.0f} s ({cpu / span:.2f} núcleos de media)\n")
    print(f"{'proceso':24} {'CPU s':>8} {'parte':>7} {'núcleos':>8}")
    for name, s in sorted(total.items(), key=lambda kv: -kv[1])[:20]:
        print(f"{name:24} {s:8.0f} {s / cpu:7.1%} {s / span:8.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
