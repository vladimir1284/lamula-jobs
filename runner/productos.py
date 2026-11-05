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


def soltar(origen: Path, destino: Path, vistos: dict[str, tuple[int, int]]) -> list[Path]:
    """Mueve a `destino` los productos que ya están enteros y quietos; el resto se queda en `origen`.

    Se llama cada pocos segundos *mientras* `play_a2` reproduce, para publicar por lotes (puerta de F3).
    Un producto sale solo si pasa `entero()` y si su (tamaño, mtime) no cambió desde la llamada anterior
    (`vistos` guarda esa foto). La segunda condición cubre el caso raro de un escritor que aún no ha
    terminado y cuya cabecera ya declara la longitud final. Los truncados de verdad nunca salen: los
    encuentra `revisar()` al final y el job falla (D11). El movimiento es un `rename` en el mismo
    sistema de ficheros, así que el destino nunca ve un fichero a medias.
    """
    destino.mkdir(parents=True, exist_ok=True)
    sueltos: list[Path] = []
    for ruta in sorted(p for p in origen.iterdir() if p.is_file() and es_producto(p)):
        st = ruta.stat()
        foto = (st.st_size, st.st_mtime_ns)
        previa, vistos[ruta.name] = vistos.get(ruta.name), foto
        if previa == foto and entero(ruta):
            nuevo = destino / ruta.name
            ruta.rename(nuevo)
            vistos.pop(ruta.name, None)
            sueltos.append(nuevo)
    return sueltos
