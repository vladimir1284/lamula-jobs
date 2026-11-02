#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["metpy>=1.7.1", "numpy>=2.0"]
# ///
"""Perfil de intensidad de una ventana de Level II, para elegir casos preparados.

El tamaño del fichero no sirve de proxy —lo domina el patrón de barrido, medido el 2026-11-02
en `docs/referencia/catalogo-verificado.md`—, así que la intensidad hay que mirarla de verdad:
se decodifica el barrido más bajo de cada volumen muestreado y se cuenta cuánto eco fuerte hay
cerca del radar.

    f0/intensidad.py KAMX 2017-09-10T12:00 2017-09-10T22:00 --cada 4

Baja un volumen de cada `--cada`, lo mide y lo borra. No deja nada en disco.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalogo import L2_BUCKET, Volume, _parse_when, list_window


@dataclass(frozen=True)
class Medida:
    vol: Volume
    max_dbz: float
    frac_fuerte: float  # fracción de celdas ≥ umbral dentro del radio
    frac_nucleo: float  # ídem con umbral + 15 dBZ


def medir(path: Path, radio_km: float, umbral_dbz: float) -> tuple[float, float, float]:
    import numpy as np
    from metpy.io import Level2File

    f = Level2File(str(path))
    sweep = f.sweeps[0]
    hdr = sweep[0][4][b"REF"][0]
    data = np.array([ray[4][b"REF"][1] for ray in sweep], dtype="float32")
    rng = np.arange(hdr.num_gates) * hdr.gate_width + hdr.first_gate
    cerca = data[:, rng <= radio_km]
    return (
        float(np.nanmax(data)),
        float(np.nanmean(cerca >= umbral_dbz)),
        float(np.nanmean(cerca >= umbral_dbz + 15)),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="intensidad", description=__doc__.split("\n")[0])
    parser.add_argument("site")
    parser.add_argument("start")
    parser.add_argument("end")
    parser.add_argument("--cada", type=int, default=4, help="muestrear un volumen de cada N")
    parser.add_argument("--radio", type=float, default=150.0, help="radio en km")
    parser.add_argument("--umbral", type=float, default=35.0, help="dBZ de eco fuerte")
    args = parser.parse_args(argv)

    vols = list_window(args.site, _parse_when(args.start), _parse_when(args.end))
    muestras = vols[:: args.cada]
    if not muestras:
        print(f"{args.site}: sin volúmenes en la ventana")
        return 1
    print(
        f"{args.site}: {len(muestras)} muestras de {len(vols)} volúmenes, "
        f"≥{args.umbral:.0f} dBZ dentro de {args.radio:.0f} km\n"
    )
    print("hora UTC    MB     max dBZ   % fuerte   % núcleo")
    medidas: list[Medida] = []
    with TemporaryDirectory() as tmp:
        scratch = Path(tmp) / "vol"
        for vol in muestras:
            with urllib.request.urlopen(L2_BUCKET + vol.key, timeout=300) as resp:
                scratch.write_bytes(resp.read())
            try:
                max_dbz, fuerte, nucleo = medir(scratch, args.radio, args.umbral)
            except (ValueError, KeyError, IndexError, OSError) as exc:
                print(f"{vol.scan_time:%H:%M:%S}  {vol.size_bytes / 1e6:6.1f}  ilegible: {exc}")
                continue
            medidas.append(Medida(vol, max_dbz, fuerte, nucleo))
            print(
                f"{vol.scan_time:%H:%M:%S}  {vol.size_bytes / 1e6:6.1f}  "
                f"{max_dbz:7.1f}   {fuerte:7.1%}   {nucleo:7.1%}"
            )
    if not medidas:
        return 1
    pico = max(medidas, key=lambda m: m.frac_fuerte)
    print(
        f"\npico de eco fuerte a las {pico.vol.scan_time:%H:%M:%S} UTC "
        f"({pico.frac_fuerte:.1%} del área dentro de {args.radio:.0f} km)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
