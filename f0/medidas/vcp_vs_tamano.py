#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["metpy>=1.7.1", "numpy>=2.0"]
# ///
"""Tamaño de volumen por VCP, para un día y un sitio.

De aquí salió "el tamaño del fichero no mide la tormenta": en KTBW el 2022-09-28
los volúmenes de VCP 212 pesan 23,4 MB y los de VCP 112, 18,8 MB, y la
diferencia es el patrón de barrido, no la intensidad del eco. Para medir la
tormenta está `f0/intensidad.py`.

Toma una de cada cuatro claves del día: con una petición Range de 64 KiB por
volumen, el día entero sale en menos de un minuto.
"""

import collections
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import catalogo as cat

SITIO = sys.argv[1] if len(sys.argv) > 1 else "KTBW"
DIA = sys.argv[2] if len(sys.argv) > 2 else "2022-09-28"

vols = cat.list_day(SITIO, datetime.strptime(DIA, "%Y-%m-%d").replace(tzinfo=UTC))
print(f"{SITIO} {DIA}: {len(vols)} volúmenes")

por_vcp = collections.defaultdict(list)
for v in vols[::4]:
    por_vcp[cat.probe_vcp(v.key)].append((v.scan_time, v.size_bytes / 1e6))

for vcp, items in sorted(por_vcp.items(), key=lambda kv: (kv[0] is None, kv[0])):
    mb = sorted(m for _, m in items)
    print(
        f"VCP {vcp}: n={len(items)} {items[0][0]:%H:%M}–{items[-1][0]:%H:%M}  "
        f"MB min={mb[0]:.1f} mediana={mb[len(mb) // 2]:.1f} max={mb[-1]:.1f}"
    )
