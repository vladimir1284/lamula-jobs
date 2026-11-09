"""Bucle del runner: toma un job de la cola, lo ejecuta entero y vuelve a esperar.

Corre dentro de la imagen `job-runner` con el Python del pipeline (trae psycopg y boto3); no importa
FastAPI. Habla con Postgres con el rol `jobs_runner` (cola) y con el rol `job_<id>` del job que corre
(publicar). No crea schemas ni roles: eso es de jobs-api y del barrido.

Un job termina o falla, nunca cuelga: cada paso lleva timeout y el latido detecta la cancelación.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from . import queue, tenancy
from .config import Secrets, env

LATIDO_S = 10
TOL_COORD = 0.001  # una milésima de grado: la precisión de change_radar.dat
STATS = re.compile(r"procesados=(\d+) fallidos=(\d+)")


class JobFallido(RuntimeError):
    """El job no puede continuar; el mensaje se guarda en `jobs.error` y se muestra al cliente."""


class JobCancelado(Exception):
    pass


@dataclass
class Destino:
    """Dónde publica un job: base, rol de escritura y bucket de rasters."""
    pg_host: str
    pg_port: str
    pg_db: str
    pg_user: str
    pg_password: str
    r2_bucket: str


@dataclass
class Cfg:
    runner_dsn: str                  # jobs_runner
    pg_host: str
    pg_port: str
    pg_db: str
    secrets: Secrets
    s3: object
    staging_bucket: str
    r2_endpoint: str
    r2_bucket: str
    r2_key: str
    r2_secret: str
    trabajo: Path = Path("/data/jobs")
    runner_cmd: tuple[str, ...] = ("runner",)
    l3proc_cmd: tuple[str, ...] = ("l3proc",)
    change_radar_dat: Path = Path.home() / "tools/cfg/change_radar.dat"
    nombre: str = ""
    s3_fuente: object = None         # cliente anónimo del catálogo público; None = el real
    fuente_bucket: str = ""
    casos: Destino | None = None     # D19: base y bucket de los casos preparados; None = este worker no los procesa

    def destino_de(self, job: dict) -> Destino:
        """Un job normal publica en su schema (rol propio); un caso, en la base y el bucket de casos (D19)."""
        if job.get("destino") == "casos":
            if self.casos is None:
                raise JobFallido("este worker no tiene configurada la base de casos (CASOS_PG_*, CASOS_R2_BUCKET)")
            return self.casos
        jid = job["id"]
        return Destino(self.pg_host, self.pg_port, self.pg_db, tenancy.rol_rw(jid), tenancy.password(self.secrets.rw, "rw", jid), self.r2_bucket)

    @classmethod
    def from_env(cls) -> "Cfg":
        import boto3
        ep, k, s = env("R2_ENDPOINT"), env("R2_ACCESS_KEY_ID"), env("R2_SECRET_ACCESS_KEY")
        casos = Destino(env("CASOS_PG_HOST", env("PG_HOST")), env("CASOS_PG_PORT", env("PG_PORT", "5432")), env("CASOS_PG_DB"),
                        env("CASOS_PG_USER"), env("CASOS_PG_PASSWORD"), env("CASOS_R2_BUCKET")) if os.environ.get("CASOS_PG_DB") else None
        return cls(runner_dsn=env("JOBS_RUNNER_DSN"), casos=casos, pg_host=env("PG_HOST"), pg_port=env("PG_PORT", "5432"), pg_db=env("PG_DB"),
                   secrets=Secrets(env("JOBS_RW_SECRET").encode(), b"", b""),  # el runner NO conoce RO ni la de resultado
                   s3=boto3.client("s3", endpoint_url=ep, aws_access_key_id=k, aws_secret_access_key=s, region_name="auto"),
                   staging_bucket=env("STAGING_BUCKET"), r2_endpoint=ep, r2_bucket=env("R2_BUCKET"), r2_key=k, r2_secret=s,
                   trabajo=Path(env("JOBS_WORKDIR", "/data/jobs")), nombre=f"{socket.gethostname()}:{os.getpid()}")


def coordenadas_esperadas(dat: Path, icao: str) -> tuple[float, float]:
    """(lat, lon) en grados de la línea del sitio en change_radar.dat (`kmlb,28113,-80654,...`, milésimas)."""
    for ln in dat.read_text().splitlines():
        p = ln.split(",")
        if p and p[0].strip().lower() == icao.lower() and len(p) >= 3:
            return int(p[1]) / 1000, int(p[2]) / 1000
    raise JobFallido(f"{icao} no está en {dat.name}: no se puede verificar la georreferenciación")


def verificar_coordenadas(rw: psycopg.Connection, icao: str, esperadas: tuple[float, float], compartida: bool = False) -> None:
    """Regla del repo: el `site_id` y el lat/lon que acaban en `radars` tienen que ser los del job.

    En el schema de un job `radars` tiene que tener una sola fila. La base de casos (D19) es compartida por
    cinco radares: ahí se mira solo la fila del sitio del job, y que falte también es un fallo."""
    if compartida:
        filas = rw.execute("SELECT site_id, icao, lat, lon FROM radars WHERE site_id = %s", (icao[1:],)).fetchall()
    else:
        filas = rw.execute("SELECT site_id, icao, lat, lon FROM radars").fetchall()
    if len(filas) != 1:
        raise JobFallido(f"radars debería tener 1 fila y tiene {len(filas)}: {[f['site_id'] for f in filas]}")
    f = filas[0]
    if f["site_id"] != icao[1:] or (f["icao"] not in (None, icao)):
        raise JobFallido(f"radars dice {f['site_id']}/{f['icao']} y el job es {icao}")
    if abs(f["lat"] - esperadas[0]) > TOL_COORD or abs(f["lon"] - esperadas[1]) > TOL_COORD:
        raise JobFallido(f"coordenadas {f['lat']},{f['lon']} y se esperaban {esperadas}: change_radar no surtió efecto")


def _bajar_fuente(cfg: Cfg, e: dict, dest: Path, intentos: int = 3) -> None:
    """Baja un volumen del catálogo público con reintentos y comprueba el tamaño que dio el alta."""
    from .catalogo import BUCKET, anonimo
    s3 = cfg.s3_fuente or anonimo()
    ultimo: Exception | None = None
    for i in range(intentos):
        try:
            s3.download_file(cfg.fuente_bucket or BUCKET, e["source_key"], str(dest))
            if e["bytes"] and dest.stat().st_size != e["bytes"]:
                raise OSError(f"tamaño {dest.stat().st_size} y se esperaban {e['bytes']}")
            return
        except Exception as exc:  # noqa: BLE001
            ultimo = exc
            dest.unlink(missing_ok=True)
            time.sleep(min(2 ** i, 5))
    raise JobFallido(f"no se pudo bajar {e['source_key']} de la fuente pública: {ultimo}") from ultimo


def bajar_entradas(cfg: Cfg, entradas: list[dict], destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    for e in entradas:
        nombre = e["staging_key"].rsplit("/", 1)[-1]
        if e.get("source_key"):  # de la fuente pública (F4): se baja directo, sin pasar por staging
            _bajar_fuente(cfg, e, destino / nombre)
            continue
        try:
            cfg.s3.download_file(cfg.staging_bucket, e["staging_key"], str(destino / nombre))
        except Exception as exc:  # noqa: BLE001 — cualquier fallo de red o de clave es «el job no tiene sus entradas»
            raise JobFallido(f"no se pudo bajar {e['staging_key']}: {exc}") from exc


class Vigilante(threading.Thread):
    """Latido cada LATIDO_S s. Si hay que cancelar, o el job ya no es nuestro, lo anota y avisa."""

    def __init__(self, dsn: str, job_id: str, runner: str, al_cancelar) -> None:
        super().__init__(daemon=True)
        self.dsn, self.job_id, self.runner, self.al_cancelar = dsn, job_id, runner, al_cancelar
        self.parar = threading.Event()
        self.cancelar = False

    def run(self) -> None:
        with psycopg.connect(self.dsn, autocommit=True, row_factory=dict_row) as c:
            while not self.parar.wait(LATIDO_S):
                try:
                    if queue.latir(c, self.job_id, self.runner):
                        self.cancelar = True
                        self.al_cancelar()
                        return
                except psycopg.Error:
                    pass  # un tropiezo de red no cancela el job; si dura, el barrido lo reclamará


def _correr(cmd: list[str], *, log: Path, cwd: Path, env_extra: dict | None = None, timeout: float, vig: Vigilante | None = None, proc_box: list | None = None,
            cada=None, cada_s: float = 15.0) -> int:
    """Subproceso en su propio grupo, con timeout y con parada ordenada si el vigilante pide cancelar.

    Con `cada`, lo llama cada `cada_s` s mientras el subproceso vive (publicación por lotes). Si lanza, el
    subproceso sigue vivo: quien llama lo para (`ejecutar` lo hace en su `finally`).
    """
    e = {**os.environ, **(env_extra or {})}
    with log.open("ab") as fh:
        p = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=e, cwd=cwd, start_new_session=True)  # nbtcp escribe su log en el cwd
        if proc_box is not None:
            proc_box.append(p)
        limite = time.monotonic() + timeout
        while True:
            resto = limite - time.monotonic()
            try:
                return p.wait(timeout=max(0.1, min(cada_s, resto)) if cada else timeout)
            except subprocess.TimeoutExpired:
                if resto <= cada_s or not cada:
                    _parar(p)
                    raise JobFallido(f"{cmd[0]} {cmd[1] if len(cmd) > 1 else ''}: sin acabar en {timeout:.0f} s")
                cada()


def _parar(p: subprocess.Popen, gracia: float = 150) -> None:
    """SIGTERM al grupo (el runner lo convierte en cierre ordenado del ORPG) y SIGKILL si no sale."""
    if p.poll() is not None:
        return
    try:
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(timeout=gracia)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
    except ProcessLookupError:
        pass


def limpiar_orpg() -> None:
    """Red de seguridad entre jobs: ningún proceso del ORPG de un job sobrevive al siguiente."""
    for n in ("play_a2", "nbtcp", "mrpg"):
        subprocess.run(["pkill", "-x", n], capture_output=True)


def fijar_last_seen(rw, icao: str, fin: str, compartida: bool = False) -> None:
    """Fija `radars.last_seen_at` del sitio. En base compartida varios casos comparten radar (KTBW: Ian y
    Milton): gana la fecha más tardía, no la del último caso que corre. ISO-8601 ordena igual como texto."""
    if compartida:
        rw.execute("UPDATE radars SET last_seen_at = GREATEST(last_seen_at, %s) WHERE site_id = %s", (fin, icao[1:]))
    else:
        rw.execute("UPDATE radars SET last_seen_at = %s WHERE site_id = %s", (fin, icao[1:]))


class Publicador:
    """Publica por lotes lo que el runner va dejando en `prod/` mientras el ORPG reproduce (puerta de F3).

    `paso()` coge los ficheros nuevos, los copia a un directorio de lote (`l3proc watch` consume su entrada)
    y llama a `publicar(dir)`, que devuelve `(procesados, fallidos)`. Un lote con fallidos hace fallar el job.
    `tras_lote()` corre después de cada lote bueno: verifica coordenadas y fija `last_seen_at`, de modo que un
    `change_radar` que no surtió efecto se ve con el primer lote y no con el último.
    """

    def __init__(self, prod: Path, trabajo: Path, publicar, tras_lote, *, cancelado=lambda: False, aviso=print) -> None:
        self.prod, self.trabajo, self.publicar, self.tras_lote = prod, trabajo, publicar, tras_lote
        self.cancelado, self.aviso = cancelado, aviso
        self.hechos: set[str] = set()
        self.lotes = 0
        self.procesados = 0
        self.t0 = time.monotonic()

    def paso(self) -> int:
        if self.cancelado():
            raise JobCancelado()
        nuevos = sorted(p for p in (self.prod.iterdir() if self.prod.is_dir() else []) if p.is_file() and p.name not in self.hechos)
        if not nuevos:
            return 0
        self.lotes += 1
        lote = self.trabajo / f"lote-{self.lotes:03d}"
        lote.mkdir(parents=True)
        for p in nuevos:
            shutil.copy2(p, lote / p.name)
        proc, fall = self.publicar(lote)
        shutil.rmtree(lote, ignore_errors=True)
        if fall or proc < 1:
            raise JobFallido(f"lote {self.lotes}: {proc} procesados y {fall} fallidos")
        self.hechos.update(p.name for p in nuevos)
        self.procesados += proc
        self.tras_lote()
        self.aviso(f"lote {self.lotes}: +{len(nuevos)} productos, {self.procesados} en total, a los {time.monotonic() - self.t0:.0f} s", flush=True)
        return len(nuevos)


def ejecutar(cfg: Cfg, rconn: psycopg.Connection, job: dict) -> str:
    """Ejecuta un job reclamado. Devuelve el estado final; no deja nada en disco."""
    jid, icao = job["id"], job["icao"]
    w = cfg.trabajo / jid
    box: list[subprocess.Popen] = []
    vig = Vigilante(cfg.runner_dsn, jid, cfg.nombre, lambda: box and _parar(box[0]))
    t0 = time.monotonic()
    try:
        queue.empezar(rconn, jid, cfg.nombre)
        w.mkdir(parents=True, exist_ok=True)
        vig.start()
        entradas = queue.entradas_de(rconn, jid)
        bajar_entradas(cfg, entradas, w / "in")
        n = len(entradas)
        dst = cfg.destino_de(job)
        env_pg = {"R2_ENDPOINT": cfg.r2_endpoint, "R2_BUCKET": dst.r2_bucket, "R2_ACCESS_KEY_ID": cfg.r2_key, "R2_SECRET_ACCESS_KEY": cfg.r2_secret,
                  "PG_HOST": dst.pg_host, "PG_PORT": dst.pg_port, "PG_DB": dst.pg_db, "PG_USER": dst.pg_user, "PG_PASSWORD": dst.pg_password}

        def publicar(lote: Path) -> tuple[int, int]:
            """El pipeline escribe con el rol del job, con `search_path` fijo a su schema (D4)."""
            log = w / "l3proc.log"
            log.write_text("")
            rc = _correr([*cfg.l3proc_cmd, "watch", str(lote), "--once"], log=log, cwd=w, timeout=1800, env_extra=env_pg)
            m = STATS.search(log.read_text(errors="replace"))
            if rc != 0 or not m:
                raise JobFallido("l3proc no publicó limpio: " + _cola(log))
            return int(m[1]), int(m[2])

        def tras_lote() -> None:
            with psycopg.connect(host=dst.pg_host, port=dst.pg_port, dbname=dst.pg_db, user=dst.pg_user, password=dst.pg_password, autocommit=True, row_factory=dict_row) as rw:
                compartida = job.get("destino") == "casos"
                verificar_coordenadas(rw, icao, coordenadas_esperadas(cfg.change_radar_dat, icao), compartida)
                # El selector de días del viewer se ancla a last_seen_at; sin esto un job histórico sale vacío.
                fijar_last_seen(rw, icao, job["vol_to"].strftime("%Y-%m-%dT%H:%M:%S"), compartida)

        pub = Publicador(w / "prod", w, publicar, tras_lote, cancelado=lambda: vig.cancelar)
        rc = _correr([*cfg.runner_cmd, "orpg", "--icao", icao, "--entradas", str(w / "in"), "--salida", str(w / "prod"),
                      "--logs", str(w / "log"), "--max-volumenes", str(n)],
                     log=w / "runner.log", cwd=w, timeout=n * 12 * 60 + 1800, proc_box=box, cada=pub.paso)
        if vig.cancelar:
            raise JobCancelado()
        if rc != 0:
            raise JobFallido("el ORPG no produjo los productos: " + _cola(w / "runner.log"))
        pub.paso()  # el último lote: lo que salió desde el último sondeo
        if not pub.procesados:
            raise JobFallido("l3proc no publicó ningún producto")
        if vig.cancelar:
            raise JobCancelado()
        queue.terminar(rconn, jid, cfg.nombre)
        return "ready"
    except JobCancelado:
        queue.terminar(rconn, jid, cfg.nombre, cancelado=True)
        return "cancelled"
    except JobFallido as exc:
        queue.terminar(rconn, jid, cfg.nombre, error=str(exc)[:1500])
        return "failed"
    except BaseException as exc:  # noqa: BLE001 — un error imprevisto es un job fallido, y el bucle sigue
        queue.terminar(rconn, jid, cfg.nombre, error=f"error interno: {type(exc).__name__}: {exc}"[:1500])
        return "failed"
    finally:
        vig.parar.set()
        if box:
            _parar(box[0], gracia=30)
        limpiar_orpg()
        shutil.rmtree(w, ignore_errors=True)
        print(f"job {jid} {icao}: {time.monotonic() - t0:.0f} s", flush=True)


def _cola(log: Path, n: int = 400) -> str:
    try:
        return log.read_text(errors="replace")[-n:]
    except OSError:
        return "(sin log)"


def medir() -> dict:
    """Foto del contenedor para la tanda de desgaste: procesos y memoria residente por nombre."""
    por: dict[str, int] = {}
    total = n = 0
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            nombre = (d / "comm").read_text().strip()
            m = re.search(r"VmRSS:\s+(\d+)", (d / "status").read_text())
        except OSError:
            continue
        rss = int(m[1]) if m else 0  # hilos del kernel y zombis no tienen VmRSS
        n += 1
        total += rss
        por[nombre] = por.get(nombre, 0) + rss
    top = dict(sorted(por.items(), key=lambda kv: -kv[1])[:6])
    return {"procs": n, "rss_kib": total, "mrpg_kib": por.get("mrpg", 0), "owr_server_kib": por.get("owr_server", 0), "top_kib": top}


def bucle(cfg: Cfg, *, max_jobs: int | None = None, espera: float = 5.0, metricas: Path | None = None, parar: threading.Event | None = None) -> int:
    parar = parar or threading.Event()
    hechos = 0
    with psycopg.connect(cfg.runner_dsn, autocommit=True, row_factory=dict_row) as c:
        while not parar.is_set() and (max_jobs is None or hechos < max_jobs):
            job = queue.tomar(c, cfg.nombre)
            if job is None:
                parar.wait(espera)
                continue
            limpiar_orpg()
            estado = ejecutar(cfg, c, job)
            hechos += 1
            if metricas:
                with metricas.open("a") as fh:
                    fh.write(json.dumps({"job": job["id"], "icao": job["icao"], "estado": estado, "t": time.time(), **medir()}) + "\n")
    return hechos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jobs-worker")
    ap.add_argument("--max-jobs", type=int)
    ap.add_argument("--espera", type=float, default=5.0)
    ap.add_argument("--metricas", type=Path, help="añade una línea JSON por job con procesos y memoria")
    a = ap.parse_args(argv)
    parar = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: parar.set())  # entre jobs; durante uno, el job acaba (o lo reclama el barrido)
    bucle(Cfg.from_env(), max_jobs=a.max_jobs, espera=a.espera, metricas=a.metricas, parar=parar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
