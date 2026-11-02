#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["metpy>=1.7.1"]
# ///
"""Vuelve a comprobar todo lo que esta fase da por sabido.

Cada afirmación de `docs/referencia/catalogo-verificado.md` y de
`docs/referencia/contrato-pipeline.md` tiene aquí una comprobación que la repite contra el
bucket real. Si algo cambia —el bucket, MetPy, el formato del archivo— esto se entera.

    f0/comprobar.py            # todas
    f0/comprobar.py wmo altura # solo esas

Devuelve 1 si alguna falla. Tarda alrededor de un minuto: son peticiones de red de verdad.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalogo import L2_BUCKET, _get, _list_keys, list_day, probe_vcp

L3_BUCKET = "https://unidata-nexrad-level3.s3.amazonaws.com/"
REF_L3_KEY = "AMX_N0B_2026_11_01_00_00_43"
REF_ABX_PREFIX = "ABX_N0B_2026_11_01_12"


def _head(url: str, headers: dict[str, str] | None = None) -> int:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


def c_noaa() -> str:
    """`noaa-nexrad-level2` sigue negando el acceso anónimo."""
    url = "https://noaa-nexrad-level2.s3.amazonaws.com/?list-type=2&max-keys=1"
    code = _head(url)
    assert code == 403, f"esperaba 403, llegó {code}"
    return f"listar devuelve {code}"


def c_eras() -> str:
    """El sufijo del archivo cambia con el año: V03.gz en 2010, V06.gz en 2014, V06 en 2017."""
    esperado = {2010: "V03.gz", 2014: "V06.gz", 2017: "V06"}
    visto = {}
    for year, suf in esperado.items():
        prefix = f"{year}/06/15/KAMX/"
        nombres = [k.rsplit("/", 1)[-1] for k, _ in _list_keys(L2_BUCKET, prefix)]
        colas = {n.split("_", 2)[-1] for n in nombres if n.count("_") >= 2}
        visto[year] = colas
        assert suf in colas, f"{year}: esperaba {suf}, encontré {sorted(colas)}"
    return ", ".join(f"{y}:{esperado[y]}" for y in sorted(esperado))


def c_gzip_v06() -> str:
    """Los V06 envueltos en gzip se listan y se les puede leer el VCP."""
    vols = list_day("KAMX", datetime(2015, 6, 15, tzinfo=UTC))
    assert vols, "sin volúmenes el 2015-06-15"
    assert vols[0].key.endswith("_V06.gz"), f"esperaba _V06.gz, vi {vols[0].key}"
    vcp = probe_vcp(vols[0].key)
    assert vcp is not None, "no se pudo leer el VCP de un .gz"
    return f"{len(vols)} volúmenes, VCP {vcp} leído del primero"


def c_vcp_range() -> str:
    """El VCP de un volumen moderno sale con una petición Range, sin bajar los 20 MB."""
    vols = list_day("KAMX", datetime(2026, 11, 1, tzinfo=UTC))
    vcp = probe_vcp(vols[0].key)
    assert vcp is not None, "VCP ilegible"
    assert vols[0].size_bytes > 1_000_000, "el volumen debería pesar megas"
    return f"VCP {vcp} de un fichero de {vols[0].size_bytes / 1e6:.1f} MB"


def c_wmo() -> str:
    """Sin encabezado WMO, MetPy no asigna siteID y el pipeline se queda sin clave primaria."""
    from metpy.io import Level3File

    raw = _get(L3_BUCKET + REF_L3_KEY)
    primero = raw.find(b"\r\r\n")
    corte = raw.find(b"\r\r\n", primero + 3) + 3
    assert 0 < corte <= 64, f"encabezado WMO inesperado, corte en {corte}"
    tmp = Path("/tmp/.comprobar_wmo.bin")
    try:
        tmp.write_bytes(raw[corte:])
        f = Level3File(str(tmp))
        assert f.header.code == 153, f"código {f.header.code}"
        try:
            site = f.siteID
        except AttributeError:
            return f"encabezado de {corte} bytes; sin él, siteID no existe"
        raise AssertionError(f"siteID existía sin encabezado: {site!r}")
    finally:
        tmp.unlink(missing_ok=True)


def c_altura() -> str:
    """La altura del producto está en pies: ABX da ~5951, que son ~1814 m, no 5951 m."""
    from metpy.io import Level3File

    claves = [k for k, _ in _list_keys(L3_BUCKET, REF_ABX_PREFIX)]
    assert claves, "sin producto de ABX a esa hora"
    tmp = Path("/tmp/.comprobar_altura.bin")
    try:
        tmp.write_bytes(_get(L3_BUCKET + claves[0]))
        altura = Level3File(str(tmp)).height
    finally:
        tmp.unlink(missing_ok=True)
    metros = altura * 0.3048
    assert 1700 < metros < 1900, f"{altura} no cuadra con la cota de ABX al convertir: {metros}"
    return f"ABX declara {altura}; en pies son {metros:.0f} m, que sí es su cota"


def c_l3_profundidad() -> str:
    """El archivo de Level III no llega a 2021; empieza en marzo de 2022."""
    antes = [k for k, _ in _list_keys(L3_BUCKET, "TBW_N0B_2021_11_15")]
    despues = [k for k, _ in _list_keys(L3_BUCKET, "TBW_N0B_2022_03_15")]
    assert not antes, f"había {len(antes)} claves en 2021"
    assert despues, "no había claves en marzo de 2022"
    return "2021 vacío, marzo de 2022 con datos"


def c_parejas() -> str:
    """Cada volumen reciente tiene su Level III con el mismo sello de tiempo."""
    dia = datetime(2026, 11, 1, tzinfo=UTC)
    vols = list_day("KAMX", dia)[:20]
    claves = {k for k, _ in _list_keys(L3_BUCKET, f"AMX_N0B_{dia:%Y_%m_%d}")}
    hechas = sum(1 for v in vols if f"AMX_N0B_{v.scan_time:%Y_%m_%d_%H_%M_%S}" in claves)
    assert hechas == len(vols), f"solo {hechas} de {len(vols)}"
    return f"{hechas} de {len(vols)} volúmenes con su N0B"


COMPROBACIONES: dict[str, Callable[[], str]] = {
    "noaa": c_noaa,
    "eras": c_eras,
    "gzip": c_gzip_v06,
    "vcp": c_vcp_range,
    "wmo": c_wmo,
    "altura": c_altura,
    "l3": c_l3_profundidad,
    "parejas": c_parejas,
}


def main(argv: list[str]) -> int:
    pedidas = argv[1:] or list(COMPROBACIONES)
    desconocidas = [n for n in pedidas if n not in COMPROBACIONES]
    if desconocidas:
        raise SystemExit(f"comprobar: no conozco {', '.join(desconocidas)}")
    fallos = 0
    for nombre in pedidas:
        func = COMPROBACIONES[nombre]
        try:
            detalle = func()
        except Exception as exc:  # noqa: BLE001 — aquí cualquier fallo es un fallo
            fallos += 1
            print(f"FALLA  {nombre:9} {func.__doc__.splitlines()[0]}\n       {exc}")
        else:
            print(f"ok     {nombre:9} {detalle}")
    print(f"\n{len(pedidas) - fallos}/{len(pedidas)} comprobaciones")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
