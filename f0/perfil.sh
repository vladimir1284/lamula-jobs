#!/bin/bash
# Perfil de CPU del ORPG durante una reproducción: qué procesos gastan el tiempo.
#
# Dentro del contenedor, con shell de login y el ORPG ya arrancado (mrpg -p -v startup):
#
#   f0/perfil.sh <directorio de volúmenes> <salida.csv> [flags de play_a2, por defecto -m]
#
# Cada 2 s anota, por nombre de proceso, los ticks de CPU acumulados (utime+stime de
# /proc/<pid>/stat). El análisis es `f0/perfil.py`. No toca la configuración del ORPG; solo lee /proc.
dir=$1; out=$2; flags=${3:--m}
[ -d "$dir" ] && [ -n "$out" ] || { sed -n 2,9p "$0"; exit 2; }

sampler() {
  while :; do
    t=$(date +%s)
    for s in /proc/[0-9]*/stat; do
      cat "$s" 2>/dev/null
    done | awk -v t="$t" '{
        # el nombre va entre paréntesis y puede llevar espacios
        match($0, /\(.*\)/); name=substr($0, RSTART+1, RLENGTH-2)
        rest=substr($0, RSTART+RLENGTH+2); n=split(rest, f, " ")
        ticks[name]+=f[12]+f[13]
      } END { for (k in ticks) print t "," k "," ticks[k] }' >> "$out"
    sleep 2
  done
}

: > "$out"
sampler &
spid=$!
trap 'kill $spid 2>/dev/null' EXIT
start=$(date +%s)
play_a2 $flags -d "$dir" > "${out%.csv}.play.out" 2>&1
echo "play_a2 $flags: $(( $(date +%s) - start )) s" | tee "${out%.csv}.resumen"
# el ORPG sigue procesando después de que play_a2 salga: hasta que la CPU se calme
sleep 120
echo "reposo: +120 s" >> "${out%.csv}.resumen"
