#!/usr/bin/env python3
"""Emulador mínimo de RDA que reproduce volúmenes Level II (Archive II) hacia un ORPG.

Es la idea de `vladimir1284/RDA_Backend` (el ORPG, por `cm_tcp`, se conecta como cliente al
puerto 10010 de un «RDA») aplicada a Level II: un volumen Archive II ya es una secuencia de
mensajes del RDA (tipos 2, 3, 5, 13, 15, 18 y 31 en el formato del ICD 2620002), así que no se
recodifica nada. Se mandan tal cual, con el encuadre CTM de la sesión.

    f0/rda_replay.py <directorio con volúmenes> [--sleep 0.0] [--port 10010]

Solo usa la biblioteca estándar. Una vez conectado el ORPG y recibida la orden de operar (mensaje
6), manda los volúmenes en orden de nombre, sin más espera que `--sleep` segundos por radial.
Escribe en stdout una línea por volumen con radiales, bytes y segundos. `--sleep` es la única
perilla de ritmo: no hay control de flujo, para ver si el ORPG lo necesita.
"""

from __future__ import annotations

import argparse
import bz2
import socket
import struct
import sys
import threading
import time
from pathlib import Path

CTM = struct.Struct(">3I")  # tipo de sesión, parámetro, longitud
FRAME = 2432  # trama fija de los mensajes que no son 31
LOGIN, LOGIN_ACK, DATA, DATA_ACK, KEEPALIVE = 0, 1, 2, 3, 4
TCM_ID = 20983610  # cmt_shared.c: login y su acuse llevan este valor en `param`; si no, se descartan
LENGTH_MASK = 0x7FFFFFFF
TRACE = False
# petición de datos (mensaje 9) → tipo de mensaje que se contesta
REQUEST = {129: 2, 130: 3, 132: 13, 136: 15, 144: 18, 160: 5}
METADATA = (2, 3, 5, 13, 15, 18)


def messages(path: Path):
    """Rinde (tipo, bytes del mensaje sin CTM) de un volumen: 16 B de cabecera + cuerpo."""
    raw = path.read_bytes()
    pos = 24  # cabecera del volumen
    while pos + 4 <= len(raw):
        n = abs(struct.unpack(">i", raw[pos : pos + 4])[0])
        pos += 4
        if n == 0:
            break
        block = bz2.decompress(raw[pos : pos + n])
        pos += n
        q = 0
        while q + 28 <= len(block):
            size, _chan, typ = struct.unpack(">HBB", block[q + 12 : q + 16])
            step = size * 2 + 12 if typ == 31 else FRAME
            if typ != 0 and size:
                yield typ, block[q + 12 : q + 12 + size * 2]
            q += step


class Rda:
    def __init__(self, volumes: list[Path], port: int, pause: float, delay: float = 2.0, linger: float = 5.0, inline_meta_off: bool = False, password: str = "passwd") -> None:
        self.volumes, self.pause, self.delay, self.linger, self.password = volumes, pause, delay, linger, password
        self.inline_meta_off = inline_meta_off
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", port))
        self.sock.listen(1)
        self.lock = threading.Lock()
        self.go = threading.Event()
        self.alive = True
        self.meta: dict[int, list[bytes]] = {t: [] for t in METADATA}
        for typ, msg in messages(volumes[0]):
            if typ in self.meta:
                self.meta[typ].append(msg)
        print("metadatos:", {t: len(v) for t, v in self.meta.items()}, flush=True)

    def send(self, typ: int, par: int, body: bytes = b"") -> None:
        with self.lock:
            self.conn.sendall(CTM.pack(typ, par, len(body)) + body)

    def synthetic(self, mtype: int, body: bytes) -> bytes:
        now = time.time()
        julian, ms = int(now // 86400) + 1, int(now % 86400 * 1000)
        return struct.pack(">H2B2HI2H", 8 + len(body) // 2, 0, mtype, 0, julian, ms, 1, 1) + body

    def loopback(self, mtype: int) -> None:
        self.send(DATA, 0, self.synthetic(mtype, struct.pack(">52H", 52, *range(51))))

    def send_meta(self, types) -> None:
        for t in types:
            for msg in self.meta[t]:
                self.send(DATA, 0, msg)

    def read(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.conn.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("el ORPG cerró la conexión")
            buf += chunk
        return buf

    def reader(self) -> None:
        """Atiende lo que manda el ORPG mientras el hilo principal transmite."""
        try:
            while self.alive:
                typ, par, length = CTM.unpack(self.read(12))
                length &= LENGTH_MASK
                if TRACE and typ != KEEPALIVE:
                    print(f"  <- {time.strftime('%H:%M:%S')} ctm={typ},{par},{length}", body[3:4].hex() if length >= 16 else "", flush=True)
                body = self.read(length) if length else b""
                if typ == LOGIN:
                    words = body.decode("utf-8", "replace").split()
                    if words[-1].strip("\x00") != self.password:
                        print("clave incorrecta", flush=True)
                        continue
                    ack = f"{words[0]} {words[1]} connected\0".encode()
                    self.send(LOGIN_ACK, TCM_ID, ack)
                    self.loopback(11)
                    print("ORPG conectado", flush=True)
                elif typ == KEEPALIVE:
                    self.send(KEEPALIVE, par)
                elif typ == DATA:
                    mtype = body[3] if len(body) >= 16 else -1
                    if par:
                        self.send(DATA_ACK, par)
                    if mtype == 12:  # prueba RPG→RDA: se devuelve el mismo cuerpo, byte a byte
                        self.send(DATA, 0, self.synthetic(12, body[16:]))
                    elif mtype == 11:
                        self.send_meta(METADATA)
                    elif mtype == 9 and len(body) >= 18:
                        want = REQUEST.get(struct.unpack(">H", body[16:18])[0])
                        if want:
                            self.send_meta((want,))
                    elif mtype == 6:
                        print("orden de control recibida", flush=True)
                        self.go.set()
        except (ConnectionError, OSError) as exc:
            if self.alive:
                print("lector:", exc, flush=True)
            self.alive = False
            self.go.set()

    def run(self) -> int:
        # cm_tcp reintenta cada pocos segundos: se acepta hasta que llegue la orden de operar
        while True:
            self.conn, addr = self.sock.accept()
            print("conexión de", addr, flush=True)
            self.alive = True
            self.go.clear()
            threading.Thread(target=self.reader, daemon=True).start()
            self.go.wait()
            if self.alive:
                break
            self.conn.close()
        time.sleep(self.delay)  # que el ORPG procese el estado (y se pueda arrancar nbtcp)
        t_all = time.time()
        for vol in self.volumes:
            t0, radials, size = time.time(), 0, 0
            for typ, msg in messages(vol):
                if typ in METADATA or not self.alive:
                    if typ in METADATA and typ != 2 and not self.inline_meta_off:
                        self.send(DATA, 0, msg)
                    continue
                try:
                    self.send(DATA, 0, msg)
                except OSError as exc:
                    print("envío:", exc, flush=True)
                    return 1
                radials += 1
                size += len(msg)
                if self.pause:
                    time.sleep(self.pause)
            print(f"{vol.name}: {radials} radiales, {size / 1e6:.1f} MB, {time.time() - t0:.1f} s", flush=True)
            if not self.alive:
                return 1
        print(f"total {time.time() - t_all:.1f} s", flush=True)
        time.sleep(self.linger)  # cerrar la línea mata a p_server: hay que esperar a que el ORPG acabe
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dir")
    ap.add_argument("--port", type=int, default=10010)
    ap.add_argument("--delay", type=float, default=2.0, help="segundos entre la orden de operar y el primer radial")
    ap.add_argument("--linger", type=float, default=5.0, help="segundos con la línea abierta tras el último radial")
    ap.add_argument("--sin-metadatos", action="store_true", help="no reenviar los mensajes 3, 5, 13, 15 y 18 que trae cada volumen")
    ap.add_argument("--sleep", type=float, default=0.0, help="segundos entre radiales")
    ap.add_argument("--trace", action="store_true", help="anota lo que manda el ORPG (salvo keepalives)")
    args = ap.parse_args()
    global TRACE
    TRACE = args.trace
    vols = sorted(p for p in Path(args.dir).iterdir() if p.is_file() and not p.name.startswith("playlist"))
    if not vols:
        print("sin volúmenes")
        return 2
    return Rda(vols, args.port, args.sleep, args.delay, args.linger, args.sin_metadatos).run()


if __name__ == "__main__":
    sys.exit(main())
