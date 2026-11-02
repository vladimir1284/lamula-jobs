#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["metpy>=1.7.1"]
# ///
"""Herramienta de análisis del catálogo público de Level II.

**No es código del servicio.** Es instrumental de la Fase 0: sirve para medir el
catálogo antes de escribir nada del runner, para preparar los ficheros de una
espiga manual y para documentar con números las decisiones que siguen abiertas
(hueco aceptable entre volúmenes, qué hacer con un cambio de VCP a mitad de un
trabajo).

Bucket `unidata-nexrad-level2`, lectura anónima (ver `docs/arquitectura/fuentes-entrada.md`:
`noaa-nexrad-level2` responde 403 a la misma llamada).

Subcomandos:

    list   SITIO DIA              volúmenes de un sitio en un día UTC
    scan   SITIO DESDE HASTA      cadencia, huecos y VCP de una ventana
    cases                         los casos preparados, medidos
    pairs  SITIO DIA              parejas Level II / Level III para la prueba de equivalencia
    fetch  SITIO DESDE HASTA DIR  descarga la ventana y escribe la playlist de play_a2

El VCP se lee con una petición Range de 64 KiB: el primer registro LDM de un
volumen V06 trae el mensaje 5 completo y ocupa unos pocos KiB, así que no hace
falta bajar los ~6 MB del fichero para saber con qué patrón se observó.
"""

from __future__ import annotations

import argparse
import struct
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

L2_BUCKET = "https://unidata-nexrad-level2.s3.amazonaws.com/"
L3_BUCKET = "https://unidata-nexrad-level3.s3.amazonaws.com/"
S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}

# Rango inicial de la petición Range para el probe de VCP. Si el primer registro
# LDM no cabe, el probe reintenta con el cuádruple.
PROBE_BYTES = 65536

# Casos preparados de `docs/arquitectura/fuentes-entrada.md`. Las ventanas salen de medir el
# eco con `intensidad.py`, no de la hora de recalada: no son el mismo instante.
CASES: dict[str, tuple[str, str, str]] = {
    "irma": ("KAMX", "2017-09-10T17:00", "2017-09-10T18:30"),
    "harvey": ("KHGX", "2017-08-27T12:00", "2017-08-27T13:30"),
    "michael": ("KEVX", "2018-10-10T19:00", "2018-10-10T20:30"),
    "ian": ("KTBW", "2022-09-28T21:30", "2022-09-28T23:00"),
    "milton": ("KTBW", "2024-10-09T23:00", "2024-10-10T00:30"),
}


@dataclass(frozen=True)
class Volume:
    key: str
    size_bytes: int
    scan_time: datetime  # del nombre del fichero, no del LastModified del objeto

    @property
    def name(self) -> str:
        return self.key.rsplit("/", 1)[-1]


def _get(url: str, headers: dict[str, str] | None = None, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _list_keys(bucket: str, prefix: str) -> Iterator[tuple[str, int]]:
    """ListObjectsV2 anónimo, paginado. Devuelve (clave, tamaño)."""
    token: str | None = None
    while True:
        params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            params["continuation-token"] = token
        root = ET.fromstring(_get(bucket + "?" + urllib.parse.urlencode(params)))
        for node in root.findall("s3:Contents", S3_NS):
            key = node.findtext("s3:Key", default="", namespaces=S3_NS)
            size = int(node.findtext("s3:Size", default="0", namespaces=S3_NS))
            yield key, size
        if root.findtext("s3:IsTruncated", default="false", namespaces=S3_NS) != "true":
            return
        token = root.findtext("s3:NextContinuationToken", namespaces=S3_NS)
        if not token:
            return


def _scan_time(name: str) -> datetime | None:
    """`KAMX20170910_120000_V06` → datetime UTC. None si no cuadra."""
    parts = name.split("_")
    if len(parts) < 3:
        return None
    try:
        return datetime.strptime(parts[0][-8:] + parts[1], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def is_v06(name: str) -> bool:
    """D9: solo Message 31. Hasta 2015 el archivo guarda los V06 envueltos en gzip."""
    return name.endswith(("_V06", "_V06.gz"))


def list_day(site: str, day: datetime, only_v06: bool = True) -> list[Volume]:
    """Volúmenes de un sitio en un día UTC, en orden cronológico."""
    prefix = f"{day:%Y/%m/%d}/{site}/"
    out: list[Volume] = []
    for key, size in _list_keys(L2_BUCKET, prefix):
        name = key.rsplit("/", 1)[-1]
        if only_v06 and not is_v06(name):
            continue
        if name.endswith("_MDM"):  # metadatos del día, no es un volumen
            continue
        when = _scan_time(name)
        if when is None:
            continue
        out.append(Volume(key, size, when))
    out.sort(key=lambda v: v.scan_time)
    return out


def list_window(site: str, start: datetime, end: datetime) -> list[Volume]:
    """Volúmenes de una ventana, cubriendo el cruce de medianoche UTC."""
    days: list[datetime] = []
    cursor = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    vols = [v for day in days for v in list_day(site, day)]
    return [v for v in vols if start <= v.scan_time <= end]


# Un mensaje de metadatos (tipos 15, 13, 18, 3, 5, 2) ocupa un segmento fijo: 12 bytes de
# relleno CTM + 2416 de mensaje. El tipo 31 (los radiales) no se pagina así, pero el VCP está
# en el mensaje 5, que va en el registro de metadatos, antes de cualquier radial.
METADATA_SEGMENT = 2432
VOL_HEADER_BYTES = 24


def _vcp_from_metadata(block: bytes) -> int | None:
    """Recorre los mensajes de metadatos buscando el 5 (VCP). None si no cabe en el bloque."""
    off = VOL_HEADER_BYTES
    while off + METADATA_SEGMENT <= len(block):
        msg_type = block[off + 15]
        if msg_type == 5:
            # Cuerpo del mensaje 5: tamaño (2), tipo de patrón (2), número de patrón (2).
            return int(struct.unpack(">H", block[off + 32 : off + 34])[0])
        off += METADATA_SEGMENT
    return None


def probe_vcp(key: str) -> int | None:
    """VCP del volumen, con una sola petición Range. No baja el volumen entero.

    Dos disposiciones conviven en el archivo:

    - Hasta 2015, el fichero entero va envuelto en gzip y por dentro los mensajes van sin
      comprimir. Se descomprime el prefijo que se tenga y se busca el mensaje 5.
    - Desde 2016, el fichero es la cabecera de volumen más registros LDM comprimidos con bzip2
      por separado. El primero es el registro de metadatos y ocupa unos pocos KB, así que se
      recorta por su frontera exacta y lo decodifica MetPy.
    """
    want = PROBE_BYTES
    if key.endswith(".gz"):
        raw = _get(L2_BUCKET + key, headers={"Range": f"bytes=0-{want - 1}"})
        try:
            return _vcp_from_metadata(zlib.decompressobj(31).decompress(raw, 1 << 22))
        except (zlib.error, struct.error, IndexError):
            return None

    from metpy.io import Level2File

    for _ in range(3):
        raw = _get(L2_BUCKET + key, headers={"Range": f"bytes=0-{want - 1}"})
        if len(raw) < 28:
            return None
        size = abs(struct.unpack(">i", raw[24:28])[0])
        if 28 + size > len(raw):
            want *= 4
            continue
        tmp = Path(f"/tmp/.vcp_probe_{abs(hash(key))}.bin")
        try:
            tmp.write_bytes(raw[: 28 + size])
            return int(Level2File(str(tmp)).vcp_info.num)
        except (ValueError, struct.error, OSError, AttributeError):
            return None
        finally:
            tmp.unlink(missing_ok=True)
    return None


def _parse_when(text: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    raise SystemExit(f"catalogo: fecha no reconocida: {text!r}")


def _gaps(vols: list[Volume]) -> list[float]:
    return [(b.scan_time - a.scan_time).total_seconds() for a, b in pairwise(vols)]


def _summary(site: str, vols: list[Volume], vcps: list[int | None] | None = None) -> str:
    if not vols:
        return f"{site}: sin volúmenes en la ventana"
    gaps = _gaps(vols)
    total_mb = sum(v.size_bytes for v in vols) / 1e6
    span = (vols[-1].scan_time - vols[0].scan_time).total_seconds()
    lines = [
        f"{site}  {vols[0].scan_time:%Y-%m-%d %H:%M:%S} → {vols[-1].scan_time:%H:%M:%S} UTC",
        f"  volúmenes V06 : {len(vols)}",
        f"  tamaño        : {total_mb:.1f} MB ({total_mb / len(vols):.1f} MB/volumen)",
    ]
    if gaps:
        cadencia = (
            f"  cadencia      : min {min(gaps):.0f} s, "
            f"mediana {sorted(gaps)[len(gaps) // 2]:.0f} s, max {max(gaps):.0f} s"
        )
        lines += [cadencia, f"  duración a -T : {span / 60:.0f} min de reproducción"]
    if vcps is not None:
        seen: list[tuple[int | None, datetime]] = []
        for vol, vcp in zip(vols, vcps, strict=False):
            if not seen or seen[-1][0] != vcp:
                seen.append((vcp, vol.scan_time))
        lines.append("  VCP           : " + ", ".join(f"{v} desde {t:%H:%M:%S}" for v, t in seen))
        if len(seen) > 1:
            lines.append(f"  !! {len(seen) - 1} cambio(s) de VCP dentro de la ventana")
    return "\n".join(lines)


def cmd_list(args: argparse.Namespace) -> int:
    vols = list_day(args.site, _parse_when(args.day))
    for vol in vols:
        print(f"{vol.scan_time:%H:%M:%S}  {vol.size_bytes / 1e6:6.2f} MB  {vol.key}")
    print(f"\n{len(vols)} volúmenes V06", file=sys.stderr)
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    vols = list_window(args.site, _parse_when(args.start), _parse_when(args.end))
    vcps = [probe_vcp(v.key) for v in vols] if args.vcp else None
    print(_summary(args.site, vols, vcps))
    if args.gaps and len(vols) > 1:
        print("\n  huecos mayores de 10 min:")
        for a, b in pairwise(vols):
            gap = (b.scan_time - a.scan_time).total_seconds()
            if gap > 600:
                print(f"    {a.scan_time:%H:%M:%S} → {b.scan_time:%H:%M:%S}  ({gap / 60:.1f} min)")
    return 0


def cmd_cases(args: argparse.Namespace) -> int:
    names = [args.case] if args.case else list(CASES)
    for name in names:
        site, start, end = CASES[name]
        vols = list_window(site, _parse_when(start), _parse_when(end))
        vcps = [probe_vcp(v.key) for v in vols] if args.vcp else None
        print(f"\n== {name} ==")
        print(_summary(site, vols, vcps))
    return 0


def best_window(vols: list[Volume], n: int, max_gap_s: float) -> list[Volume]:
    """Los n volúmenes consecutivos que más bytes suman, sin ningún hueco mayor que el tope.

    El tamaño comprimido de un volumen crece con el eco: bzip2 comprime mucho un cielo vacío y
    poco una tormenta. Sirve de proxy barato de intensidad, y se calcula con lo que ya devuelve
    el listado del bucket, sin bajar nada.
    """
    best: list[Volume] = []
    best_bytes = -1
    for i in range(len(vols) - n + 1):
        chunk = vols[i : i + n]
        if any(g > max_gap_s for g in _gaps(chunk)):
            continue
        total = sum(v.size_bytes for v in chunk)
        if total > best_bytes:
            best, best_bytes = chunk, total
    return best


def cmd_ventana(args: argparse.Namespace) -> int:
    vols = list_window(args.site, _parse_when(args.start), _parse_when(args.end))
    if len(vols) < args.n:
        print(f"{args.site}: solo {len(vols)} volúmenes en el rango, se piden {args.n}")
        return 1
    chunk = best_window(vols, args.n, args.max_gap)
    if not chunk:
        print(f"{args.site}: no hay {args.n} consecutivos sin huecos de más de {args.max_gap:.0f} s")
        return 1
    print(_summary(args.site, chunk))
    print()
    for vol in chunk:
        print(f"{vol.scan_time:%Y-%m-%d %H:%M:%S}  {vol.size_bytes / 1e6:6.2f} MB  {vol.key}")
    return 0


def cmd_eras(args: argparse.Namespace) -> int:
    """Desde qué año un sitio ofrece V06, que es lo único que el selector puede ofrecer (D9)."""
    probe_day = (args.month, args.day)
    for year in range(args.desde, args.hasta + 1):
        prefix = f"{year}/{probe_day[0]:02d}/{probe_day[1]:02d}/{args.site}/"
        suffixes: dict[str, int] = {}
        for key, _ in _list_keys(L2_BUCKET, prefix):
            name = key.rsplit("/", 1)[-1]
            tail = name.split("_", 2)[-1] if name.count("_") >= 2 else "(otro)"
            suffixes[tail] = suffixes.get(tail, 0) + 1
        if not suffixes:
            print(f"{year}: sin datos ese día")
            continue
        desc = ", ".join(f"{n}×{t}" for t, n in sorted(suffixes.items()))
        usable = sum(n for t, n in suffixes.items() if t in ("V06", "V06.gz"))
        print(f"{year}: {desc}   → {usable} seleccionables")
    return 0


def cmd_pairs(args: argparse.Namespace) -> int:
    """Parejas Level II / Level III del mismo barrido, para la puerta de equivalencia de F0."""
    day = _parse_when(args.day)
    vols = list_day(args.site, day)
    l3_site = args.site[1:]  # KAMX → AMX en el bucket de Level III
    prefix = f"{l3_site}_{args.product}_{day:%Y_%m_%d}"
    l3 = {}
    for key, _ in _list_keys(L3_BUCKET, prefix):
        stamp = key[len(prefix) + 1 :].replace("_", "")
        try:
            when = datetime.strptime(f"{day:%Y%m%d}{stamp}", "%Y%m%d%H%M%S")
        except ValueError:
            continue
        l3[when.replace(tzinfo=UTC)] = key
    matched = 0
    for vol in vols:
        hit = l3.get(vol.scan_time)
        if hit:
            matched += 1
            if matched <= args.limit:
                print(f"{vol.scan_time:%H:%M:%S}  L2 {vol.key}\n           L3 {hit}")
    print(
        f"\n{matched} de {len(vols)} volúmenes tienen {args.product} con el mismo sello de tiempo",
        file=sys.stderr,
    )
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    vols = list_window(args.site, _parse_when(args.start), _parse_when(args.end))
    if args.max and len(vols) > args.max:
        vols = vols[: args.max]
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    for i, vol in enumerate(vols, 1):
        out = dest / vol.name
        if out.exists() and out.stat().st_size == vol.size_bytes:
            print(f"[{i}/{len(vols)}] {vol.name} (ya estaba)", file=sys.stderr)
            continue
        print(f"[{i}/{len(vols)}] {vol.name} {vol.size_bytes / 1e6:.1f} MB", file=sys.stderr)
        out.write_bytes(_get(L2_BUCKET + vol.key, timeout=300))
    playlist = dest / "playlist"
    playlist.write_text("".join(f"{dest.resolve() / v.name}\n" for v in vols))
    print(playlist)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="catalogo", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="volúmenes de un sitio en un día UTC")
    p.add_argument("site")
    p.add_argument("day")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("scan", help="cadencia, huecos y VCP de una ventana")
    p.add_argument("site")
    p.add_argument("start")
    p.add_argument("end")
    p.add_argument(
        "--vcp", action="store_true", help="leer el VCP de cada volumen (una petición Range)"
    )
    p.add_argument("--gaps", action="store_true", help="listar los huecos mayores de 10 min")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("cases", help="medir los casos preparados")
    p.add_argument("case", nargs="?", choices=sorted(CASES))
    p.add_argument("--vcp", action="store_true")
    p.set_defaults(func=cmd_cases)

    p = sub.add_parser("ventana", help="los n volúmenes seguidos con más eco de un rango")
    p.add_argument("site")
    p.add_argument("start")
    p.add_argument("end")
    p.add_argument("-n", type=int, default=12, help="volúmenes de la ventana")
    p.add_argument("--max-gap", type=float, default=900.0, help="hueco máximo tolerado, en segundos")
    p.set_defaults(func=cmd_ventana)

    p = sub.add_parser("eras", help="qué formato ofrece un sitio año por año")
    p.add_argument("site")
    p.add_argument("--desde", type=int, default=2008)
    p.add_argument("--hasta", type=int, default=2017)
    p.add_argument("--month", type=int, default=6)
    p.add_argument("--day", type=int, default=15)
    p.set_defaults(func=cmd_eras)

    p = sub.add_parser("pairs", help="parejas Level II / Level III para la prueba de equivalencia")
    p.add_argument("site")
    p.add_argument("day")
    p.add_argument("--product", default="N0B")
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(func=cmd_pairs)

    p = sub.add_parser("fetch", help="descargar una ventana y escribir la playlist de play_a2")
    p.add_argument("site")
    p.add_argument("start")
    p.add_argument("end")
    p.add_argument("dest")
    p.add_argument("--max", type=int, default=0, help="tope de volúmenes")
    p.set_defaults(func=cmd_fetch)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
