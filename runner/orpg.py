"""Pasos 3, 4, 5, 7, 8 y 9 del ciclo: adaptar el sitio, arrancar el ORPG, abrir la salida, reproducir.

Cada espera lleva timeout. Cada orden se ejecuta con el `PATH` y las variables de la shell de
login del contenedor; este módulo no las inventa.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

ARRANQUE_OK = "RPG startup completed"
PUERTO_NBTCP = "4491"
RPS_LIST = "rps_lamula.list"


class OrpgError(RuntimeError):
    """El ORPG no hizo lo que se esperaba; el job falla, no se reintenta aquí."""


def _cfg() -> Path:
    try:
        return Path(os.environ["CFG_DIR"])
    except KeyError as exc:
        raise OrpgError("sin CFG_DIR: hay que lanzarlo desde una shell de login del contenedor") from exc


def _correr(cmd: list[str], *, timeout: float, entrada: str | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, input=entrada, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise OrpgError(f"{cmd[0]}: sin respuesta en {timeout:.0f} s") from exc


def adaptar_sitio(icao: str) -> None:
    """`change_radar`. Un ICAO que el CODE no conoce falla aquí y no más adelante, con coordenadas ajenas."""
    res = _correr(["change_radar", "-r", icao.lower(), "-S", "-R"], timeout=60)
    if res.returncode != 0:
        raise OrpgError(f"change_radar {icao}: código {res.returncode}\n{res.stdout[-500:]}{res.stderr[-500:]}")


def arrancar(log: Path, *, timeout: float = 300) -> None:
    """`mrpg -p -v startup`: el `-p` borra los data stores y hace efectivo el cambio de sitio.

    `mrpg` no sale tras arrancar, así que se lanza aparte, sin terminal, y se espera la línea de
    fin de arranque en su salida. Con la máquina cargada el arranque llegó a tardar 2 min medidos.
    """
    log.parent.mkdir(parents=True, exist_ok=True)
    log.unlink(missing_ok=True)
    with log.open("wb") as fh:
        subprocess.Popen(["mrpg", "-p", "-v", "startup"], stdout=fh, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if ARRANQUE_OK in log.read_text(errors="replace"):
            return
        time.sleep(2)
    _correr(["pkill", "-x", "mrpg"], timeout=10)
    raise OrpgError(f"el ORPG no terminó de arrancar en {timeout:.0f} s (ver {log})")


def abrir_salida(icao: str, destino: Path, *, clave: str = "passwd", timeout: float = 90) -> None:
    """`nbtcp -A -b -D`: productos con encabezado WMO a `destino`, vaciado al empezar (aislamiento).

    El último argumento tiene que ser el hostname: de dos caracteres o menos se toma por un
    enlace `cm_tcp`. La RPS list es lo único que lee de la entrada estándar.
    """
    destino.mkdir(parents=True, exist_ok=True)
    _correr(["pkill", "-x", "nbtcp"], timeout=10)
    cmd = ["nbtcp", "-A", "-b", "-D", str(destino), "-s", icao, "-p", PUERTO_NBTCP, "-w", clave, socket.gethostname()]
    res = _correr(cmd, timeout=timeout, entrada=RPS_LIST + "\n")
    if res.returncode != 0:
        raise OrpgError(f"nbtcp: código {res.returncode}\n{res.stdout[-500:]}{res.stderr[-500:]}")


def reproducir(entradas: Path, log: Path, *, timeout: float) -> None:
    """`play_a2 -m -d` (D6). Sin `-R`: el producto conserva el `vol_time` original."""
    with log.open("wb") as fh:
        try:
            res = subprocess.run(["play_a2", "-m", "-d", str(entradas)], stdout=fh, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise OrpgError(f"play_a2 no acabó en {timeout:.0f} s") from exc
    if res.returncode != 0:
        raise OrpgError(f"play_a2: código {res.returncode} (ver {log})")


def esperar_reposo(destino: Path, *, reposo: float, timeout: float) -> None:
    """Hasta que no aparece ningún producto nuevo durante `reposo` segundos.

    Es una heurística, y se sabe: el ORPG sigue procesando después de que `play_a2` sale y no
    hay nada que diga «he terminado». Lo que sí está acotado es el peor caso (`timeout`).
    """
    def cuenta() -> tuple[int, int]:
        fs = [p for p in destino.iterdir() if p.is_file()]
        return len(fs), sum(p.stat().st_size for p in fs)

    visto, desde = cuenta(), time.monotonic()
    limite = desde + timeout
    while time.monotonic() < limite:
        time.sleep(5)
        ahora = cuenta()
        if ahora != visto:
            visto, desde = ahora, time.monotonic()
        elif time.monotonic() - desde >= reposo:
            return
    raise OrpgError(f"el ORPG seguía produciendo a los {timeout:.0f} s")


def cerrar() -> None:
    """`mrpg shutdown` solo manda la orden; las tareas operativas tardan unos 7 s en salir.

    El ORPG ha parado cuando `rpg_ps` ya no lista más tareas que `mrpg` (el del arranque) y
    `owr_server`, que se queda como resto. `mrpg -p startup` no sale nunca (y se desdobla, así
    que el proceso que lanzó `arrancar` no es el que queda): se retira por nombre al final.
    """
    _correr(["pkill", "-x", "nbtcp"], timeout=10)
    _correr(["mrpg", "shutdown"], timeout=60)
    limite = time.monotonic() + 90
    while time.monotonic() < limite:
        tareas = [ln.split()[0] for ln in _correr(["rpg_ps"], timeout=30).stdout.splitlines()[1:]
                  if ln.strip() and not ln.startswith("RPG:")]
        if not set(tareas) - {"mrpg", "owr_server"}:
            _correr(["pkill", "-x", "mrpg"], timeout=10)
            return
        time.sleep(2)
    raise OrpgError("el ORPG sigue con tareas 90 s después de shutdown")


def limpiar(*rutas: Path) -> None:
    for r in rutas:
        shutil.rmtree(r, ignore_errors=True)
