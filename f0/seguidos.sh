#!/bin/bash
# dos jobs seguidos en el mismo contenedor
rm -rf /data/seq && mkdir -p /data/seq
for j in "KAMX ar2in a" "KHGX ar2in-khgx b"; do
  set -- $j
  s=$(date +%s)
  echo "== job $3 $1 inicio $(date +%T)"
  runner orpg --icao $1 --entradas /data/$2 --salida /data/seq/prod-$3 --logs /data/seq/log-$3 --clave passwd
  echo "== job $3 rc=$? $(( $(date +%s) - s )) s"
  rpg_ps 2>&1 | tail -4
done
echo "== fin $(date +%T)"
