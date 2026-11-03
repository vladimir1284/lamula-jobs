#!/bin/bash
# Una pasada del emulador de RDA (f0/rda_replay.py) contra el ORPG del contenedor `orpg-f0`
# con una velocidad de línea (LR) concreta en el enlace 0 de comms_link.conf.
#
#   [EXTRA="--sin-metadatos"] f0/rda_lr.sh <LR en bit/s> <etiqueta> [directorio de volúmenes, por defecto f0-run/ar2in]
#
# Reinicia el ORPG (mrpg -p startup), conecta el RDA, arranca nbtcp una vez conectada la línea
# (si se arranca antes, las peticiones se pierden) y transmite. Deja en f0-run/rda-lr-<etiqueta>.txt
# el tiempo de envío, los productos, y cuántas veces `pbd` dijo MESSAGE EXPIRED (radial
# sobrescrito antes de leerse = pérdida). Los productos quedan en f0-run/products-<etiqueta>.
lr=$1; tag=$2; dir=${3:-f0-run/ar2in}
[ -n "$lr" ] && [ -n "$tag" ] || { sed -n 2,10p "$0"; exit 2; }
cd "$(dirname "$0")/.." || exit 1
out=f0-run/rda-lr-$tag.txt

docker exec orpg-f0 bash -lc "cd \$CFG_DIR && sed -i -E 's/^(   0   0   0   0   0  Dedic  )[0-9]+ cm_tcp /\1$lr cm_tcp /' comms_link.conf"
python3 -I f0/rda_replay.py "$dir" --delay 45 --linger 150 $EXTRA > "f0-run/rda-$tag.out" 2>&1 &
emu=$!
docker exec orpg-f0 bash -lc "cd /home/orpg; pkill -x nbtcp; sleep 1; rm -f startup-$tag.out
  setsid nohup mrpg -p -v startup > startup-$tag.out 2>&1 < /dev/null &
  until grep -q 'RPG startup completed' startup-$tag.out 2>/dev/null; do sleep 2; done"
timeout 120 bash -c "until grep -q 'orden de control' f0-run/rda-$tag.out; do sleep 2; done"
docker exec orpg-f0 bash -lc "cd /home/orpg; rm -rf /data/products-$tag; mkdir -p /data/products-$tag
  echo rps_lamula.list | timeout 40 nbtcp -A -b -D /data/products-$tag -s KAMX -p 4491 -w passwd orpg-f0 > nbtcp-$tag.out 2>&1"
wait $emu
{
  echo "LR=$lr"
  grep -E '^(KAMX|total)' "f0-run/rda-$tag.out"
  echo "productos: $(ls f0-run/products-$tag | grep -vc 'GSM\|P173\|RR_')"
  echo "MESSAGE EXPIRED: $(docker exec orpg-f0 bash -lc 'strings /home/orpg/data/logs/pbd.log | grep -c EXPIRED')"
} > "$out"
cat "$out"
