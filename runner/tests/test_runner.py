"""`python3 -I -m unittest discover -s runner/tests -t .` desde la raíz del repo."""

from __future__ import annotations

import gzip
import struct
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from runner import entradas, productos


def volumen(dir: Path, icao: str, nombre: str, gz: bool = False) -> Path:
    cab = b"AR2V0006." + b"001" + b"\0" * 8 + icao.encode()
    ruta = dir / (nombre + (".gz" if gz else ""))
    ruta.write_bytes(gzip.compress(cab + b"x" * 50) if gz else cab + b"x" * 50)
    return ruta


class Entradas(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.d = Path(self.t.name)

    def tearDown(self):
        self.t.cleanup()

    def validar(self, rutas, **kw):
        return entradas.validar(rutas, icao="KAMX", max_volumenes=12, max_hueco=timedelta(minutes=30), **kw)

    def test_buenos_y_gzip(self):
        a = volumen(self.d, "KAMX", "KAMX20170910_170248_V06")
        b = volumen(self.d, "KAMX", "KAMX20170910_170927_V06", gz=True)
        self.assertEqual(len(self.validar([a, b])), 2)

    def test_icao_ajeno(self):
        a = volumen(self.d, "KHGX", "KHGX20170910_170248_V06")
        with self.assertRaisesRegex(entradas.EntradaInvalida, "KHGX"):
            self.validar([a])

    def test_nombre_y_cabecera_no_casan(self):
        a = volumen(self.d, "KHGX", "KAMX20170910_170248_V06")
        with self.assertRaisesRegex(entradas.EntradaInvalida, "cabecera"):
            self.validar([a])

    def test_orden_hueco_y_cuota(self):
        a = volumen(self.d, "KAMX", "KAMX20170910_170248_V06")
        b = volumen(self.d, "KAMX", "KAMX20170910_190000_V06")
        with self.assertRaisesRegex(entradas.EntradaInvalida, "hueco"):
            self.validar([a, b])
        with self.assertRaisesRegex(entradas.EntradaInvalida, "no es posterior"):
            self.validar([b, a])
        with self.assertRaisesRegex(entradas.EntradaInvalida, "cuota"):
            entradas.validar([a, b], icao="KAMX", max_volumenes=1, max_hueco=timedelta(hours=9))

    def test_no_es_volumen(self):
        a = self.d / "KAMX20170910_170248_V06"
        a.write_bytes(b"nada" * 20)
        with self.assertRaisesRegex(entradas.EntradaInvalida, "AR2V00"):
            self.validar([a])


class Productos(unittest.TestCase):
    def test_revisar(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            cuerpo = struct.pack(">hhii", 153, 1, 2, 100) + b"\0" * 88  # declara 100, trae 100
            (d / "bueno").write_bytes(b"\0" * 30 + cuerpo)
            (d / "corto").write_bytes(b"\0" * 30 + cuerpo[:60])
            (d / "GSM_1").write_bytes(b"x")
            (d / "P173_2").write_bytes(b"x")
            rev = productos.revisar(d)
            self.assertEqual([p.name for p in rev.buenos], ["bueno"])
            self.assertEqual([p.name for p in rev.truncados], ["corto"])
            self.assertEqual(sorted(p.name for p in rev.ignorados), ["GSM_1", "P173_2"])

    def test_soltar_solo_lo_entero_y_quieto(self):
        with tempfile.TemporaryDirectory() as t:
            o, d = Path(t) / "o", Path(t) / "d"
            o.mkdir()
            cuerpo = struct.pack(">hhii", 153, 1, 2, 100) + b"\0" * 88
            (o / "bueno").write_bytes(b"\0" * 30 + cuerpo)
            (o / "corto").write_bytes(b"\0" * 30 + cuerpo[:60])  # truncado de verdad: no sale nunca
            (o / "GSM_1").write_bytes(b"x")
            vistos: dict = {}
            self.assertEqual(productos.soltar(o, d, vistos), [])  # primera foto: nada sale aún
            self.assertEqual([p.name for p in productos.soltar(o, d, vistos)], ["bueno"])
            self.assertEqual(sorted(p.name for p in o.iterdir()), ["GSM_1", "corto"])
            self.assertEqual([p.name for p in d.iterdir()], ["bueno"])
            self.assertEqual(productos.soltar(o, d, vistos), [])
            # un escritor que sigue: la cabecera ya declara 100 pero el fichero crece; solo sale al quedarse quieto
            (o / "creciendo").write_bytes(b"\0" * 30 + cuerpo[:40])
            productos.soltar(o, d, vistos)
            (o / "creciendo").write_bytes(b"\0" * 30 + cuerpo)
            self.assertEqual(productos.soltar(o, d, vistos), [])  # cambió desde la foto anterior
            self.assertEqual([p.name for p in productos.soltar(o, d, vistos)], ["creciendo"])


if __name__ == "__main__":
    unittest.main()
