#!/usr/bin/env bash
# 실제 지형 선별 성능 특성 기록 (WSL 안에서): 5 s 마다 WSL 메모리 사용·gz RTF·sim time. 사용: rtf_mem_probe.sh <world> <out.csv> <duration_s>
W=$1; OUT=$2; D=${3:-900}; export GZ_PARTITION=adair_ugv
echo "wall,mem_used_mb,mem_avail_mb,rtf,sim_s" > $OUT
end=$(( $(date +%s) + D ))
while [ $(date +%s) -lt $end ]; do
  m=$(free -m | awk '/Mem:/ {print $3","$7}')
  s=$(timeout 3 gz topic -e -t /world/$W/stats -n 1 2>/dev/null | tr '\n' ' ')
  r=$(echo "$s" | grep -o 'real_time_factor: [0-9.e-]*' | awk '{print $2}')
  t=$(echo "$s" | grep -oE 'sim_time { *sec: [0-9]+' | awk '{print $NF}')
  echo "$(date +%s.%N | cut -c1-14),$m,${r:-},${t:-}" >> $OUT
  sleep 5
done
