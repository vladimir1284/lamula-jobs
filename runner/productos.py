"""Salida de `nbtcp`: qué ficheros son productos y cuáles llegaron enteros."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

WMO = 30  # bytes de encabezado que añade `nbtcp -A`
# Ficheros que `nbtcp` deja junto a los productos y que no lo son (estado general, respuesta de
# la petición 173, mensajes de petición de respuesta).
NO_PRODUCTO = ("GSM", "P173_", "RR_")


@dataclass
class Revision:
    buenos: list[Path] = field(default_factory=list)
    truncados: list[Path] = field(default_factory=list)
    ignorados: list[Path] = field(default_factory=list)


def es_producto(ruta: Path) -> bool:
    return not (ruta.name.startswith(NO_PRODUCTO) or "_GSM" in ruta.name)


def entero(ruta: Path) -> bool:
    """La longitud declarada en la cabecera Level III contra el tamaño real, tras el encabezado WMO."""
    with ruta.open("rb") as fh:
        cab = fh.read(WMO + 12)
    real = ruta.stat().st_size - WMO
    if len(cab) < WMO + 12:
        return False
    declarado = struct.unpack(">hhii", cab[WMO : WMO + 12])[3]
    return real == declarado


def revisar(directorio: Path) -> Revision:
    rev = Revision()
    for ruta in sorted(p for p in directorio.iterdir() if p.is_file()):
        if not es_producto(ruta):
            rev.ignorados.append(ruta)
        elif entero(ruta):
            rev.buenos.append(ruta)
        else:
            rev.truncados.append(ruta)
    return rev
