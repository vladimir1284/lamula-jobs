"""`jobs-admin`: emisión de tokens, migración, barrido, caducidad a mano y comprobación de huérfanos.

El token de acceso se muestra una sola vez; en la base queda su sha256 (docs/operacion/acceso-y-cuotas.md).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import sweep
from .config import Secrets, env
from .db import conectar, migrar
from .ids import nuevo_token_acceso, sha256, ulid


def emitir(conn, *, email: str, tier: str, org: str | None = None, note: str | None = None, days: int | None = None) -> tuple[str, str]:
    if conn.execute("SELECT 1 FROM control.tiers WHERE name = %s", (tier,)).fetchone() is None:
        raise SystemExit(f"nivel desconocido: {tier}")
    tok, tid = nuevo_token_acceso(), ulid()
    caduca = datetime.now(timezone.utc) + timedelta(days=days) if days else None
    conn.execute("INSERT INTO control.access_tokens (id, email, org, token_sha256, tier, expires_at, note) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                 (tid, email, org, sha256(tok), tier, caduca, note))
    return tid, tok


def almacen_desde_entorno() -> sweep.Almacen:
    import boto3
    s3 = boto3.client("s3", endpoint_url=env("R2_ENDPOINT"), aws_access_key_id=env("R2_ACCESS_KEY_ID"),
                      aws_secret_access_key=env("R2_SECRET_ACCESS_KEY"), region_name="auto")
    return sweep.Almacen(s3, env("R2_BUCKET"), env("STAGING_BUCKET"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jobs-admin")
    sub = ap.add_subparsers(dest="orden", required=True)
    sub.add_parser("migrate", help="aplica las migraciones de control (con el DSN de administración)")
    i = sub.add_parser("issue", help="emite un token de acceso")
    i.add_argument("--email", required=True)
    i.add_argument("--tier", required=True)
    i.add_argument("--org")
    i.add_argument("--note")
    i.add_argument("--days", type=int, help="caducidad; sin ella no caduca")
    r = sub.add_parser("revoke", help="revoca un token (por id)")
    r.add_argument("token_id")
    w = sub.add_parser("sweep", help="runners muertos, caducidad y borrado de lo cancelado o caducado")
    w.add_argument("--cada", type=int, metavar="SEGUNDOS", help="en bucle, cada tantos segundos (para un servicio); sin él, una vez")
    h = sub.add_parser("health", help="alarma de cola: jobs sin reclamar o con latido viejo; sale con 1 si hay alguno")
    h.add_argument("--cola-max", type=int, default=300, help="segundos que un job puede esperar en cola (300)")
    h.add_argument("--latido-max", type=int, default=sweep.LATIDO_AVISO_S, help=f"segundos sin latido de un job en marcha ({sweep.LATIDO_AVISO_S})")
    x = sub.add_parser("expire", help="caduca a mano un job ready o failed y borra ya su schema, roles y objetos")
    x.add_argument("job_id")
    k = sub.add_parser("caso", help="procesa un caso preparado, una vez: sin caducidad, en la base y el bucket de casos (D19)")
    k.add_argument("nombre", help="id del caso (GET /v1/catalog/cases)")
    sub.add_parser("orphans", help="schemas y roles job_* sin job vigente; sale con 1 si hay alguno")
    args = ap.parse_args(argv)
    conn = conectar(env("JOBS_ADMIN_DSN"))
    if args.orden == "migrate":
        print(json.dumps(migrar(conn)))
    elif args.orden == "issue":
        tid, tok = emitir(conn, email=args.email, tier=args.tier, org=args.org, note=args.note, days=args.days)
        print(f"id: {tid}\ntoken (no se vuelve a mostrar): {tok}")
    elif args.orden == "revoke":
        conn.execute("UPDATE control.access_tokens SET revoked_at = now() WHERE id = %s AND revoked_at IS NULL", (args.token_id,))
    elif args.orden == "sweep":
        s = Secrets.from_env()
        almacen, mig = almacen_desde_entorno(), Path(env("PIPELINE_MIGRATIONS"))
        while True:
            try:
                print(json.dumps(sweep.barrer(conn, almacen, migraciones=mig, rw=s.rw, ro=s.ro), default=str), flush=True)
            except Exception as exc:  # noqa: BLE001 — en bucle un fallo se anota y se reintenta; a mano, se propaga
                if not args.cada:
                    raise
                print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}), file=sys.stderr, flush=True)
            if not args.cada:
                break
            time.sleep(args.cada)
    elif args.orden == "health":
        h = sweep.salud(conn, cola_max_s=args.cola_max, latido_max_s=args.latido_max)
        print(json.dumps(h, default=str))
        return 1 if h["sin_reclamar"] or h["latido_viejo"] else 0
    elif args.orden == "expire":
        try:
            r = sweep.caducar(conn, almacen_desde_entorno(), args.job_id)
        except KeyError:
            print(f"no existe el job {args.job_id}", file=sys.stderr)
            return 1
        print(json.dumps(r, default=str))
        if not r["caducado"]:
            print(f"el job está {r['state']}: solo se caducan los ready o failed (uno en marcha se cancela antes)", file=sys.stderr)
            return 1
    elif args.orden == "caso":
        from . import catalogo, queue, service
        try:
            j = service.lanzar_caso(conn, args.nombre, catalogo.anonimo(), secrets=Secrets.from_env(), migraciones=Path(env("PIPELINE_MIGRATIONS")))
        except KeyError:
            print(f"no existe el caso {args.nombre}; los hay: {', '.join(catalogo.CASOS)}", file=sys.stderr)
            return 1
        except queue.Solapado:
            print(f"el caso {args.nombre} ya tiene un job vivo: no se procesa dos veces", file=sys.stderr)
            return 1
        except (queue.EntradaInvalida, catalogo.CatalogoError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001 — el índice único de casos vivos es lo que dice que ya existe
            if "jobs_un_caso_vivo" in str(exc):
                print(f"el caso {args.nombre} ya tiene un job vivo: no se procesa dos veces", file=sys.stderr)
                return 1
            raise
        print(json.dumps({"id": j["id"], "state": j["state"], "caso": j["caso"], "n_volumes": j["n_volumes"]}, default=str))
    elif args.orden == "orphans":
        h = sweep.huerfanos(conn)
        print(json.dumps(h))
        return 1 if h["schemas"] or h["roles"] else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
