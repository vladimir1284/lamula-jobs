"""Catálogo público de Level II (D10): qué sitios tienen datos un día y qué volúmenes tiene un sitio.

Lista en vivo con boto3 anónimo contra `unidata-nexrad-level2` (una petición cada consulta, ~200 ms,
docs/arquitectura/fuentes-entrada.md). Solo claves `_V06` (D9). No copia nada: eso es del alta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

BUCKET = "unidata-nexrad-level2"
# Medido en F0/F1: 12 volúmenes con `play_a2 -m -d` ≈ 80 min de nodo (docs/referencia/velocidad-reproduccion.md).
MIN_POR_VOLUMEN = 80 / 12
CLAVE = re.compile(r"^(\d{4})/(\d{2})/(\d{2})/([A-Z0-9]{4})/\4(\d{8})_(\d{6})_V06$")
_ICAO = re.compile(r"^[A-Z0-9]{4}$")

# Ventanas medidas, no horas de recalada (docs/referencia/catalogo-verificado.md; f0/catalogo.py CASES).
CASOS = {
    "irma": ("Irma", "KAMX", "2017-09-10T17:00", "2017-09-10T18:30"),
    "harvey": ("Harvey", "KHGX", "2017-08-27T12:00", "2017-08-27T13:30"),
    "michael": ("Michael", "KEVX", "2018-10-10T19:00", "2018-10-10T20:30"),
    "ian": ("Ian", "KTBW", "2022-09-28T21:30", "2022-09-28T23:00"),
    "milton": ("Milton", "KTBW", "2024-10-09T23:00", "2024-10-10T00:30"),
}


class CatalogoError(ValueError):
    pass


@dataclass(frozen=True)
class Volumen:
    key: str
    bytes: int
    hora: datetime  # del nombre, no del LastModified


def anonimo():
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config
    return boto3.client("s3", region_name="us-east-1", config=Config(signature_version=UNSIGNED, connect_timeout=5, read_timeout=15, retries={"max_attempts": 2}))


def _dia(s: str) -> date:
    try:
        d = date.fromisoformat(s)
    except ValueError:
        raise CatalogoError(f"día no válido: {s!r} (YYYY-MM-DD)")
    if d > datetime.now(timezone.utc).date():
        raise CatalogoError("día en el futuro")
    return d


def sitios(s3, dia: str, bucket: str = BUCKET) -> list[str]:
    d = _dia(dia)
    pref = f"{d:%Y/%m/%d}/"
    out: list[str] = []
    for pag in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=pref, Delimiter="/"):
        out += [p["Prefix"].split("/")[-2] for p in pag.get("CommonPrefixes", [])]
    return sorted(s for s in out if _ICAO.match(s))


def volumenes(s3, icao: str, dia: str, bucket: str = BUCKET) -> list[Volumen]:
    icao = icao.upper()
    if not _ICAO.match(icao):
        raise CatalogoError(f"ICAO no válido: {icao!r}")
    d = _dia(dia)
    pref = f"{d:%Y/%m/%d}/{icao}/"
    out: list[Volumen] = []
    for pag in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=pref):
        for o in pag.get("Contents", []):
            m = CLAVE.match(o["Key"])
            if m:
                out.append(Volumen(o["Key"], o["Size"], datetime.strptime(m[5] + m[6], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)))
    return sorted(out, key=lambda v: v.hora)


def estimar(n: int, total_bytes: int = 0) -> dict:
    return {"n_volumes": n, "bytes": total_bytes, "minutos": round(n * MIN_POR_VOLUMEN)}


def caso(s3, nombre: str, bucket: str = BUCKET) -> dict:
    """Volúmenes de un caso preparado: los de su ventana, que puede cruzar la medianoche UTC."""
    titulo, icao, desde, hasta = CASOS[nombre]
    d0, d1 = datetime.fromisoformat(desde).replace(tzinfo=timezone.utc), datetime.fromisoformat(hasta).replace(tzinfo=timezone.utc)
    dias = sorted({d0.date(), d1.date()})
    vols = [v for d in dias for v in volumenes(s3, icao, d.isoformat(), bucket) if d0 <= v.hora <= d1]
    return {"id": nombre, "titulo": titulo, "icao": icao, "desde": desde, "hasta": hasta,
            "volumes": [{"key": v.key, "bytes": v.bytes, "time": v.hora.isoformat()} for v in vols],
            "estimate": estimar(len(vols), sum(v.bytes for v in vols))}
