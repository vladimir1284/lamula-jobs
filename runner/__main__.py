"""CLI del runner: `python3 -I -m runner orpg --icao KAMX --entradas DIR --salida DIR`.

Ejecuta la mitad ORPG de un job (pasos 2 a 9 de docs/arquitectura/ciclo-runner.md): valida los
volúmenes, adapta el sitio, arranca el ORPG, reproduce y deja en `--salida` solo productos
enteros. La decodificación (paso 6) es otra orden; aquí no se toca Postgres ni R2.
"""

from __future__ import annotations

import argparse
import shlex
import shutil
import sys
import time
from datetime import timedelta
from pathlib import Path

from . import decodificar, entradas, orpg, productos


def _orpg(args: argparse.Namespace) -> int:
    t0 = time.monotonic()
    ent, sal = Path(args.entradas), Path(args.salida)
    rutas = sorted(p for p in ent.iterdir() if p.is_file() and not p.name.startswith("playlist"))
    vols = entradas.validar(rutas, icao=args.icao, max_volumenes=args.max_volumenes,
                            max_hueco=timedelta(minutes=args.max_hueco_min))
    print(f"{len(vols)} volúmenes de {args.icao}, {vols[0].inicio:%Y-%m-%d %H:%M} a {vols[-1].inicio:%H:%M} UTC", flush=True)
    tmp = sal.with_name(sal.name + ".orpg")  # lo que escribe nbtcp, antes de filtrar
    log = sal.with_name(sal.name + ".log")
    orpg.limpiar(tmp)
    try:
        orpg.adaptar_sitio(args.icao)
        orpg.arrancar(Path(args.logs) / "startup.out")
        orpg.abrir_salida(args.icao, tmp, clave=args.clave)
        # ~6,5 min por volumen de KAMX medidos en F0 (docs/referencia/velocidad-reproduccion.md)
        orpg.reproducir(ent, log, timeout=args.min_por_volumen * 60 * len(vols))
        orpg.esperar_reposo(tmp, reposo=args.reposo, timeout=600)
    except BaseException:
        try:
            orpg.cerrar()  # no tapa el error de origen con uno de cierre
        except orpg.OrpgError as exc:
            print(f"aviso: el cierre también falló: {exc}", file=sys.stderr)
        raise
    orpg.cerrar()
    rev = productos.revisar(tmp)
    sal.mkdir(parents=True, exist_ok=True)
    for p in rev.buenos:
        shutil.move(p, sal / p.name)
    orpg.limpiar(tmp)
    print(f"{len(rev.buenos)} productos, {len(rev.truncados)} truncados descartados, "
          f"{len(rev.ignorados)} ficheros que no son productos, {time.monotonic() - t0:.0f} s", flush=True)
    return 1 if rev.truncados or not rev.buenos else 0


def _decodificar(args: argparse.Namespace) -> int:
    res = decodificar.decodificar(Path(args.productos), Path(args.cogs), trabajo=Path(args.trabajo), l3proc=shlex.split(args.l3proc))
    print(f"{res.procesados} procesados, {res.fallidos} fallidos, {len(res.cogs)} salidas ({sum(p.suffix == ".tif" for p in res.cogs)} COGs)", flush=True)
    return 1 if res.fallidos or not res.cogs else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="runner")
    sub = ap.add_subparsers(dest="orden", required=True)
    o = sub.add_parser("orpg", help="mitad ORPG de un job")
    o.add_argument("--icao", required=True)
    o.add_argument("--entradas", required=True, help="directorio con los volúmenes")
    o.add_argument("--salida", required=True, help="directorio de productos buenos")
    o.add_argument("--logs", default=".", help="dónde dejar la salida del arranque")
    o.add_argument("--clave", default="passwd")
    o.add_argument("--max-volumenes", type=int, default=12)
    o.add_argument("--max-hueco-min", type=int, default=30, help="umbral provisional: pendiente del dueño")
    o.add_argument("--min-por-volumen", type=float, default=10.0, help="tope de play_a2 por volumen")
    o.add_argument("--reposo", type=float, default=90.0, help="s sin productos nuevos para dar el job por acabado")
    o.set_defaults(func=_orpg)
    d = sub.add_parser("decodificar", help="productos a COGs en disco, sin publicar")
    d.add_argument("--productos", required=True)
    d.add_argument("--cogs", required=True)
    d.add_argument("--trabajo", default=".", help="dónde dejar la copia temporal")
    d.add_argument("--l3proc", default="l3proc", help="orden del pipeline, p. ej. 'uv run --project ../nexrad-l3-pipeline l3proc'")
    d.set_defaults(func=_decodificar)
    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except (entradas.EntradaInvalida, orpg.OrpgError, decodificar.DecodificarError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
