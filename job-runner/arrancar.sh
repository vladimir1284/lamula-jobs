#!/bin/bash
# Punto de entrada para Swarm (en la pila: `entrypoint: ["/usr/local/bin/arrancar.sh"]`).
#
# El ENTRYPOINT heredado del ORPG arranca mrpg y se queda dormido: no ejecuta el CMD, y en Swarm no hay
# `docker exec`. Este script lanza ese entrypoint y, encima, el supervisor del worker; con SIGTERM los
# para en orden (primero el worker, que acaba o cancela su job; después el ORPG, que apaga mrpg limpio).
# Los argumentos de la pila se pasan al worker (p. ej. --metricas /data/wear.jsonl).
# PATH y variables del ORPG (mrpg, etc.): lo que antes daba `docker exec ... bash -lc`.
source "$HOME/.bash_profile"
/usr/local/bin/entrypoint.sh & orpg=$!
# El worker ya reinicia el ORPG por job; esperar a rssd solo evita arrancar contra un ORPG a medio levantar.
for _ in $(seq 1 90); do pgrep -x rssd >/dev/null && break; sleep 1; done
jobs-supervisor "$@" & sup=$!
parar() {
  kill -TERM "$sup" 2>/dev/null; wait "$sup" 2>/dev/null
  kill -TERM "$orpg" 2>/dev/null; wait "$orpg" 2>/dev/null
  exit 0
}
trap parar TERM INT
# Si uno de los dos muere, el contenedor entero muere y Swarm lo relanza: mejor que un worker sin ORPG.
wait -n "$sup" "$orpg"; rc=$?
echo "arrancar: salió un proceso (rc=$rc); termino para que Swarm relance el contenedor" >&2
kill -TERM "$sup" "$orpg" 2>/dev/null; wait
exit "$rc"
