#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["metpy>=1.7.1", "numpy>=2.0"]
# ///
"""Puerta de equivalencia de la Fase 0: mismo barrido por las dos vías.

La idea es sencilla. Para un volumen cualquiera existen dos productos Level III del mismo
barrido: el que distribuye el feed público y el que genera nuestro ORPG a partir del Level II
de ese mismo volumen. Si la cadena entera está bien, los dos tienen que decir lo mismo.

Este script saca una **huella** de cada producto con el decodificador del pipeline
(`nexrad-l3-pipeline`, no una reimplementación) y compara dos huellas campo a campo.

    f0/equivalencia.py referencia KAMX 2026-11-01T00:00:43 --dir ref
    f0/equivalencia.py huella ref --salida ref.json
    f0/equivalencia.py huella salida_nbtcp --salida job.json
    f0/equivalencia.py comparar ref.json job.json

El decodificador se importa del repo hermano; con `--pipeline` se le dice dónde está.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

L3_BUCKET = "https://unidata-nexrad-level3.s3.amazonaws.com/"
S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}

# Los diez que el pipeline sabe leer (ingest/products.py).
RASTER = ("N0B", "N0G", "EET", "DVL", "DAA", "DU3", "DTA")
PHENOMENA = ("NST", "NMD")
VWP = ("NVW",)
ALL_MNEMONICS = RASTER + PHENOMENA + VWP

DEFAULT_PIPELINE = Path(__file__).resolve().parents[2] / "nexrad-l3-pipeline"


def _import_pipeline(root: Path):
    """Mete el pipeline en el path y devuelve sus tres entradas de decodificación."""
    if not (root / "ingest" / "decoder" / "level3.py").exists():
        raise SystemExit(f"equivalencia: no encuentro el pipeline en {root}")
    sys.path.insert(0, str(root))
    from ingest.decoder.level3 import decode_file
    from ingest.phenomena.parse import parse_file
    from ingest.phenomena.vwp import parse_vwp_file

    return decode_file, parse_file, parse_vwp_file


def _get(url: str, timeout: int = 60) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def _list_keys(prefix: str) -> list[str]:
    params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
    root = ET.fromstring(_get(L3_BUCKET + "?" + urllib.parse.urlencode(params)))
    return [n.findtext("s3:Key", default="", namespaces=S3_NS) for n in root.findall("s3:Contents", S3_NS)]


def cmd_referencia(args: argparse.Namespace) -> int:
    """Baja los diez productos del feed público para un volumen concreto."""
    when = datetime.strptime(args.when, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    feed_site = args.site[1:] if len(args.site) == 4 else args.site
    dest = Path(args.dir)
    dest.mkdir(parents=True, exist_ok=True)
    got, missing = 0, []
    for mnemonic in ALL_MNEMONICS:
        key = f"{feed_site}_{mnemonic}_{when:%Y_%m_%d_%H_%M_%S}"
        try:
            (dest / key).write_bytes(_get(L3_BUCKET + key))
        except urllib.error.HTTPError:
            missing.append(mnemonic)
            continue
        got += 1
        print(f"  {key}")
    print(f"{got}/{len(ALL_MNEMONICS)} productos en {dest}")
    if missing:
        print(f"sin clave a esa hora: {', '.join(missing)}  (DU3 solo sale cada tres horas)")
    return 0


def _stats(levels, scale: float, offset: float) -> dict[str, Any]:
    """Resumen de un raster en unidades físicas, saltando los niveles reservados 0 y 1."""
    import numpy as np

    data = levels[levels >= 2].astype("float64") * scale + offset
    total = int(levels.size)
    if data.size == 0:
        return {"fraccion_valida": 0.0, "n_celdas": total}
    return {
        "n_celdas": total,
        "fraccion_valida": round(float(data.size) / total, 6),
        "p50": round(float(np.percentile(data, 50)), 4),
        "p90": round(float(np.percentile(data, 90)), 4),
        "p99": round(float(np.percentile(data, 99)), 4),
        "max": round(float(data.max()), 4),
        "suma": round(float(data.sum()), 2),
    }


def huella_fichero(path: Path, decoders) -> dict[str, Any] | None:
    """Huella de un producto suelto. None si el pipeline no sabe leerlo."""
    decode_file, parse_file, parse_vwp_file = decoders
    from ingest.decoder.level3 import UnsupportedProductError

    try:
        prod = decode_file(path)
    except UnsupportedProductError:
        pass
    except AttributeError as exc:  # el fallo de siteID sin encabezado WMO
        return {"fichero": path.name, "error": f"AttributeError: {exc}"}
    else:
        return {
            "fichero": path.name,
            "tipo": "raster",
            "codigo": prod.spec.code,
            "mnemonico": prod.spec.mnemonic,
            "site_id": prod.site_id,
            "lat": prod.lat,
            "lon": prod.lon,
            "altura_m": prod.height_m,
            "vcp": prod.vcp,
            "elevacion": prod.el_angle,
            "vol_time": prod.vol_time.isoformat(),
            "n_radiales": prod.n_radials,
            "n_gates": prod.n_gates,
            "scale": round(float(prod.scale), 8),
            "offset": round(float(prod.offset), 8),
            "az_min": round(float(prod.az_start.min()), 3),
            "az_max": round(float(prod.az_end.max()), 3),
            **_stats(prod.levels, prod.scale, prod.offset),
        }

    for parser, tipo in ((parse_file, "fenomenos"), (parse_vwp_file, "vwp")):
        try:
            parsed = parser(path)
        except (UnsupportedProductError, ValueError, KeyError, IndexError):
            continue
        except AttributeError as exc:
            return {"fichero": path.name, "error": f"AttributeError: {exc}"}
        if tipo == "fenomenos":
            return {
                "fichero": path.name,
                "tipo": tipo,
                "codigo": parsed.code,
                "mnemonico": {58: "NST", 141: "NMD"}.get(parsed.code, str(parsed.code)),
                "site_id": parsed.site_id,
                "vol_time": parsed.vol_time.isoformat(),
                "n_registros": len(parsed.records),
                "ids": sorted(r.cell_id for r in parsed.records),
            }
        return {
            "fichero": path.name,
            "tipo": tipo,
            "mnemonico": "NVW",
            "site_id": parsed.site_id,
            "vol_time": parsed.vol_time.isoformat(),
            "n_niveles": len(parsed.levels),
            "alturas_ft": [lv.height_ft for lv in parsed.levels],
            "velocidades_kt": [lv.wind_speed_kt for lv in parsed.levels],
        }
    return None


def cmd_huella(args: argparse.Namespace) -> int:
    decoders = _import_pipeline(Path(args.pipeline))
    target = Path(args.path)
    files = sorted(p for p in (target.iterdir() if target.is_dir() else [target]) if p.is_file())
    huellas, ignorados = [], []
    for path in files:
        h = huella_fichero(path, decoders)
        if h is None:
            ignorados.append(path.name)
        else:
            huellas.append(h)
    doc = {"origen": str(target), "huellas": huellas, "ignorados": ignorados}
    text = json.dumps(doc, indent=2, ensure_ascii=False)
    if args.salida:
        Path(args.salida).write_text(text + "\n")
        print(f"{len(huellas)} huellas en {args.salida}" + (f", {len(ignorados)} ignorados" if ignorados else ""))
    else:
        print(text)
    return 0


# Campos que tienen que coincidir exactamente, y campos numéricos con tolerancia relativa.
EXACTOS = ("tipo", "codigo", "mnemonico", "site_id", "vcp", "vol_time", "n_radiales", "n_gates",
           "scale", "offset", "n_registros", "n_niveles", "ids")
TOLERADOS = ("lat", "lon", "altura_m", "elevacion", "fraccion_valida", "p50", "p90", "p99", "max", "suma")


def cmd_comparar(args: argparse.Namespace) -> int:
    a = {h.get("mnemonico") or h["fichero"]: h for h in json.loads(Path(args.a).read_text())["huellas"]}
    b = {h.get("mnemonico") or h["fichero"]: h for h in json.loads(Path(args.b).read_text())["huellas"]}
    faltan = sorted(set(a) - set(b))
    sobran = sorted(set(b) - set(a))
    if faltan:
        print(f"solo en {args.a}: {', '.join(faltan)}")
    if sobran:
        print(f"solo en {args.b}: {', '.join(sobran)}")

    problemas = 0
    for name in sorted(set(a) & set(b)):
        ha, hb = a[name], b[name]
        diffs = []
        for field in EXACTOS:
            if (field in ha or field in hb) and ha.get(field) != hb.get(field):
                diffs.append(f"{field}: {ha.get(field)!r} vs {hb.get(field)!r}")
        for field in TOLERADOS:
            va, vb = ha.get(field), hb.get(field)
            if va is None or vb is None:
                continue
            escala = max(abs(va), abs(vb), 1e-9)
            if abs(va - vb) / escala > args.tolerancia:
                diffs.append(f"{field}: {va} vs {vb} ({abs(va - vb) / escala:.1%})")
        if diffs:
            problemas += 1
            print(f"\n{name}:")
            for d in diffs:
                print(f"  {d}")
        else:
            print(f"{name}: igual")
    print(f"\n{problemas} producto(s) con diferencias, tolerancia {args.tolerancia:.1%}")
    return 1 if problemas or faltan or sobran else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="equivalencia", description=__doc__.split("\n")[0])
    parser.add_argument("--pipeline", default=str(DEFAULT_PIPELINE), help="raíz de nexrad-l3-pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("referencia", help="bajar los diez productos del feed para un volumen")
    p.add_argument("site")
    p.add_argument("when", help="2026-11-01T00:00:43")
    p.add_argument("--dir", default="ref")
    p.set_defaults(func=cmd_referencia)

    p = sub.add_parser("huella", help="huella de un producto o de un directorio")
    p.add_argument("path")
    p.add_argument("--salida")
    p.set_defaults(func=cmd_huella)

    p = sub.add_parser("comparar", help="comparar dos huellas")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--tolerancia", type=float, default=0.001)
    p.set_defaults(func=cmd_comparar)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
