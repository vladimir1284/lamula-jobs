"""Paso 2 del ciclo (docs/arquitectura/ciclo-runner.md): validar los volúmenes antes de gastar CPU."""

from __future__ import annotations

import gzip
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

# 9 B de versión, 3 de número de volumen, 4 de fecha, 4 de hora, 4 de ICAO (comprobado 2026-11-02)
CABECERA = 24
NOMBRE = re.compile(r"^(?P<icao>[A-Z0-9]{4})(?P<f>\d{8})_(?P<h>\d{6})")


class EntradaInvalida(ValueError):
    """Un volumen o el conjunto no sirve; el mensaje dice cuál y por qué."""


@dataclass(frozen=True)
class Volumen:
    ruta: Path
    icao: str
    inicio: datetime


def leer(ruta: Path) -> Volumen:
    """Valida la cabecera de un volumen (también si va en gzip) y saca ICAO y hora de su nombre."""
    abrir = gzip.open if ruta.suffix == ".gz" else open
    try:
        with abrir(ruta, "rb") as fh:
            cab = fh.read(CABECERA)
    except (OSError, EOFError) as exc:
        raise EntradaInvalida(f"{ruta.name}: no se puede leer ({exc})") from exc
    if len(cab) < CABECERA or not cab.startswith(b"AR2V00"):
        raise EntradaInvalida(f"{ruta.name}: no empieza por AR2V00xx")
    icao = cab[20:24].decode("ascii", "replace")
    m = NOMBRE.match(ruta.name)
    if not m:
        raise EntradaInvalida(f"{ruta.name}: el nombre no es ICAOyyyymmdd_hhmmss")
    if m["icao"] != icao:
        raise EntradaInvalida(f"{ruta.name}: el nombre dice {m['icao']} y la cabecera {icao}")
    inicio = datetime.strptime(m["f"] + m["h"], "%Y%m%d%H%M%S")
    return Volumen(ruta, icao, inicio)


def validar(rutas: list[Path], *, icao: str, max_volumenes: int, max_hueco: timedelta) -> list[Volumen]:
    """Devuelve los volúmenes en orden, o lanza `EntradaInvalida`.

    Un ICAO distinto, un orden roto, un hueco por encima del umbral o más volúmenes de los que
    permite la cuota se rechazan antes de arrancar el ORPG.
    """
    if not rutas:
        raise EntradaInvalida("sin volúmenes")
    if len(rutas) > max_volumenes:
        raise EntradaInvalida(f"{len(rutas)} volúmenes, la cuota es {max_volumenes}")
    vols = [leer(r) for r in rutas]
    for v in vols:
        if v.icao != icao:
            raise EntradaInvalida(f"{v.ruta.name}: es de {v.icao} y el job es de {icao}")
    for a, b in zip(vols, vols[1:]):
        if b.inicio <= a.inicio:
            raise EntradaInvalida(f"{b.ruta.name}: no es posterior a {a.ruta.name}")
        if b.inicio - a.inicio > max_hueco:
            raise EntradaInvalida(f"hueco de {b.inicio - a.inicio} entre {a.ruta.name} y {b.ruta.name}")
    return vols
