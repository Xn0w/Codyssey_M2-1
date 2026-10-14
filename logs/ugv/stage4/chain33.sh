#!/usr/bin/env bash
# 2026-10-12 원인 분리 (c31 이탈): 옛 타일 v1 + 횡가속 1.5 (c31 과 같은 조건) / 새 타일 v2 + 횡가속 1.0 (통합 시험 설정). 코드 ../ADAIR_wt_turn
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh
until grep -q CHAIN32_DONE logs/ugv/stage4/chain32.out 2>/dev/null; do sleep 20; done
run() {  # tag tiles world spawn lat target track
  TILES=$2 WORLD=$3 UGV_LAT_ACCEL=$5 bash $RT $1 $4 logs/ugv/stage4/single_a_fleet.json bash -c "cd ../ADAIR_wt_turn && env UGV_LAT_ACCEL=$5 UGV_ROAD_SUBSET=$M/logs/ugv/stage5/$2/road_subset_$3.json ADAIR_TILES_OUT=$M/logs/ugv/stage5/$2 $PY -m ugv.tools.road_test --tag $1 --rid A-ugv1 --model adair_ugv_1 --target-node $6 --return-home --track-s $7 --world $3"
}
run c33_v1_integ_l15 tiles tz_a33 logs/ugv/stage4/tz_a33_spawn_ugv.txt 1.5 RP:682501105:65.5 600
run c33_v1_bridge_l15 tiles tz_a33 logs/ugv/stage4/tz_a33_spawn_ugv.txt 1.5 RP:682501336:293.4 900
run c33_v2_integ_l10 tiles_v2 tz_a33v2 logs/ugv/stage4/tz_a33v2_spawn_ugv.txt 1.0 RP:682501105:65.5 600
run c33_v2_bridge_l10 tiles_v2 tz_a33v2 logs/ugv/stage4/tz_a33v2_spawn_ugv.txt 1.0 RP:682501336:293.4 900
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN33_DONE $(date)"
