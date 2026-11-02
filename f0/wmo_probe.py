#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["metpy>=1.7.1"]
# ///
"""Comprueba qué pasa cuando un producto Level III no trae encabezado WMO.

Baja un producto real del feed de Unidata, lo decodifica tal cual, le quita el
encabezado WMO y lo vuelve a decodificar. Es la evidencia reproducible de
`docs/referencia/contrato-pipeline.md`.

    f0/wmo_probe.py                      # AMX_N0B de una fecha conocida
    f0/wmo_probe.py AMX_N0B_2026_11_01_00_00_43
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

L3_BUCKET = "https://unidata-nexrad-level3.s3.amazonaws.com/"
DEFAULT_KEY = "AMX_N0B_2026_11_01_00_00_43"


def strip_wmo(raw: bytes) -> tuple[bytes, int]:
    """Quita las dos líneas de texto del encabezado WMO/AWIPS. Devuelve (datos, bytes quitados)."""
    first = raw.find(b"\r\r\n")
    if first == -1:
        return raw, 0
    second = raw.find(b"\r\r\n", first + 3)
    if second == -1:
        return raw, 0
    cut = second + 3
    return raw[cut:], cut


def describe(path: Path, label: str) -> None:
    from metpy.io import Level3File

    f = Level3File(str(path))
    try:
        site = repr(f.siteID)
    except AttributeError as exc:
        site = f"AttributeError: {exc}"
    print(f"{label:22}  code={f.header.code}  src_id={f.header.src_id}  "
          f"lat={f.lat}  lon={f.lon}\n{'':22}  siteID = {site}")


def main(argv: list[str]) -> int:
    key = argv[1] if len(argv) > 1 else DEFAULT_KEY
    with urllib.request.urlopen(L3_BUCKET + key, timeout=60) as resp:
        raw = resp.read()
    stripped, cut = strip_wmo(raw)
    print(f"{key}: {len(raw)} bytes, encabezado WMO de {cut} bytes: {raw[:cut]!r}\n")
    with TemporaryDirectory() as tmp:
        original = Path(tmp) / "con_wmo"
        pelado = Path(tmp) / "sin_wmo"
        original.write_bytes(raw)
        pelado.write_bytes(stripped)
        describe(original, "con encabezado")
        describe(pelado, "sin encabezado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
