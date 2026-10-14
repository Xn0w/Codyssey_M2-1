#!/usr/bin/env bash
# (WSL 안) 진행 중 체인의 회차마다 실제 모델·월드 해석 증거를 남긴다 — 읽기 전용, 시험 프로세스를 건드리지 않음. v3/v4 manifest 결함 보완.
V=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle
R=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR
last=""
while true; do
  t=$(grep -o '^px4-[0-9]*:[^	]*' ~/.adair-ugv/procs.tsv 2>/dev/null | head -1 | cut -d: -f2)
  if [ -n "$t" ] && [ "$t" != "$last" ] && [ ! -f "$R/logs/ugv/stage4/prov/$t.json" ]; then
    sleep 5
    j=$(echo "$t" | sed -E 's/^c5[0-9]_(j[0-9]+_[0-9]+_[0-9]+)_(D8|D5|v2)_.*/\1_\2/; s/^c58_j494943_(D5|D8)_.*/j494943_1351_1352_\1/')
    sp="$R/logs/ugv/stage5/jturn/${j}_spawn.txt"
    ( cd $V && python3 -m ugv.tools.run_provenance --run-id "$t" --spawn "$sp" --out "$R/logs/ugv/stage4/prov/$t.json" ) > "$R/logs/ugv/stage4/prov/$t.txt" 2>&1
    last=$t
  fi
  [ -f "$R/logs/ugv/stage4/prov/STOP" ] && exit 0
  sleep 10
done
