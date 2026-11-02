#!/usr/bin/env python3
"""Detecta productos Level III truncados comparando la longitud declarada con el tamaño real.

`nbtcp` puede cerrar los sockets a mitad de producto ("AWIPS product completion timer expired")
y guarda lo que llegó sin dar ningún error. La cabecera del mensaje Level III dice cuánto debería
medir el producto: tras los 30 bytes del encabezado WMO vienen código (2), fecha (2), hora (4) y
longitud del mensaje (4), todo big-endian y la longitud cuenta desde el inicio del mensaje.

    f0/integridad.py f0-run/products-m
    f0/integridad.py f0-run/products-m --solo-malos

Sale con código 1 si algún producto de más de 1 KB está truncado. Los GSM de 230 bytes
(estado general, sin encabezado de producto) y otros ficheros que no traen el encabezado
se cuentan aparte.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

WMO_HEADER_SIZE = 30


def revisar(path: Path) -> tuple[str, int, int]:
    """Devuelve (estado, declarado, real) para un producto."""
    raw = path.read_bytes()
    real = len(raw) - WMO_HEADER_SIZE
    if real < 18:
        return "corto", 0, real
    code, _date, _time, declarado = struct.unpack(">hhii", raw[WMO_HEADER_SIZE : WMO_HEADER_SIZE + 12])
    if real == declarado:
        return "ok", declarado, real
    if real < declarado:
        return "TRUNCADO", declarado, real
    return "sobra", declarado, real


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    solo_malos = "--solo-malos" in argv
    if len(args) != 1:
        print(__doc__)
        return 2
    cuenta: dict[str, int] = {}
    malos = 0
    for p in sorted(Path(args[0]).iterdir()):
        if not p.is_file():
            continue
        estado, declarado, real = revisar(p)
        cuenta[estado] = cuenta.get(estado, 0) + 1
        if estado == "TRUNCADO" and real > 1024:
            malos += 1
        if not solo_malos or estado in ("TRUNCADO", "sobra"):
            print(f"{estado:9} declarado={declarado:>8} real={real:>8}  {p.name}")
    print("resumen:", ", ".join(f"{k}={v}" for k, v in sorted(cuenta.items())))
    return 1 if malos else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
