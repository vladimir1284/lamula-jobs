"""Paso 6 sin publicar (D12): `l3proc watch --once --no-publish` sobre una copia de los productos.

`l3proc watch` consume su entrada, así que nunca se le da el directorio del job.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

STATS = re.compile(r"procesados=(\d+) fallidos=(\d+)")


class DecodificarError(RuntimeError):
    pass


@dataclass(frozen=True)
class Resultado:
    procesados: int
    fallidos: int
    cogs: list[Path]  # COG (.tif) y JSON de fenómenos (NST, NMD, NVW)


def decodificar(productos: Path, cogs: Path, *, trabajo: Path, l3proc: list[str] | None = None, timeout: float = 1800) -> Resultado:
    copia = trabajo / "entrada"
    shutil.rmtree(copia, ignore_errors=True)
    shutil.copytree(productos, copia)
    cogs.mkdir(parents=True, exist_ok=True)
    try:
        res = subprocess.run([*(l3proc or ["l3proc"]), "watch", str(copia), "--once", "--no-publish", "-o", str(cogs)],
                             capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise DecodificarError(f"l3proc no acabó en {timeout:.0f} s") from exc
    m = STATS.search(res.stdout)
    if not m:
        raise DecodificarError(f"l3proc sin resumen (código {res.returncode}): {res.stdout[-300:]}{res.stderr[-300:]}")
    shutil.rmtree(copia, ignore_errors=True)
    return Resultado(int(m[1]), int(m[2]), sorted(p for p in cogs.iterdir() if p.is_file()))
