#!/bin/sh
# Supervisa a jobs-worker dentro del contenedor. El ENTRYPOINT heredado del ORPG ignora el CMD, así
# que el worker se lanza con `docker exec -d <contenedor> jobs-supervisor`; si muere, se relanza.
#
# Un worker que muere a mitad de job deja el job reclamado: lo recoge el barrido (`jobs-admin sweep`)
# tras su timeout y lo devuelve a la cola. Lo que hace este bucle es que haya worker para tomarlo.
# Con pausa creciente (máx. 60 s) para no girar en vano si falla al arrancar (config, red, Postgres).
espera=2
pid=
trap 'parar=1; [ -n "$pid" ] && kill -TERM "$pid" 2>/dev/null' TERM INT
parar=
while [ -z "$parar" ]; do
  t0=$(date +%s)
  jobs-worker "$@" &
  pid=$!
  wait "$pid"; rc=$?
  # `wait` vuelve antes si llega una señal: se espera de verdad al worker, que acaba su job en curso
  while kill -0 "$pid" 2>/dev/null; do wait "$pid"; rc=$?; done
  pid=
  [ -n "$parar" ] && break
  vivo=$(( $(date +%s) - t0 ))
  [ "$vivo" -ge 60 ] && espera=2 || { espera=$(( espera * 2 )); [ "$espera" -gt 60 ] && espera=60; }
  echo "supervisor: jobs-worker salió con $rc tras ${vivo}s; relanzo en ${espera}s" >&2
  sleep "$espera" & wait $!  # en segundo plano para que SIGTERM corte la pausa
done
