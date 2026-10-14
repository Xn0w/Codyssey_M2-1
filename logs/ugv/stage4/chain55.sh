#!/usr/bin/env bash
# 2026-10-12 원인 분리: c53 D8 494943 3/3 경유점 6 놓침(지면 차 3 cm 이내) vs c51 D5 3/3 통과. 같은 교차로에서 지면(D5·D8·v2)과 시험 도구(wt_fix·wt_turn)를 하나씩 바꾼다.
# 서버 wt_turn 30457e7, 곡선 횡가속 1.0. 495073(D5 3/3 → D8 3/3 실패)도 D5 wt_fix 로 2회
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh; ST=$M/logs/ugv/stage5; J=logs/ugv/stage5/jturn
until grep -q CHAIN54_DONE logs/ugv/stage4/chain54.out 2>/dev/null; do sleep 15; done
SUB=$ST/tiles_v2/road_subset_all_included.json
fix() {  # 시험 도구 wt_fix (c52·c53 과 같음)
  PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $4 $5 bash -c "cd ../ADAIR_wt_fix && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 120 --post-stop-s 15 --world $3"
}
turn() {  # 시험 도구 wt_turn (c51 과 같음)
  PF_SKIP_SUBSET=1 UGV_PX4_PASS_SKIP=0 SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $4 $5 bash -c "cd ../ADAIR_wt_turn && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 60 --world $3"
}
W=wj494943_1351_1352; F=$J/j494943_1351_1352_fleet.json; T=RP:682501352:20.0
fix  c55_j494943_D5_fix_a  tiles_v2_D5all $W $J/j494943_1351_1352_D5_spawn.txt $F A-ugv1 1 $T
fix  c55_j494943_D5_fix_b  tiles_v2_D5all $W $J/j494943_1351_1352_D5_spawn.txt $F A-ugv1 1 $T
turn c55_j494943_D8_turn_a tiles_v2_D8all $W $J/j494943_1351_1352_D8_spawn.txt $F A-ugv1 1 $T
turn c55_j494943_D8_turn_b tiles_v2_D8all $W $J/j494943_1351_1352_D8_spawn.txt $F A-ugv1 1 $T
turn c55_j494943_D5_turn_a tiles_v2_D5all $W $J/j494943_1351_1352_D5_spawn.txt $F A-ugv1 1 $T
fix  c55_j494943_v2_fix_a  tiles_v2      $W $J/j494943_1351_1352_v2_spawn.txt $F A-ugv1 1 $T
fix  c55_j494943_D8_fix_a  tiles_v2_D8all $W $J/j494943_1351_1352_D8_spawn.txt $F A-ugv1 1 $T
fix  c55_j495073_D5_fix_a  tiles_v2_D5all wj495073_2092_2054 $J/j495073_2092_2054_D5_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
fix  c55_j495073_D5_fix_b  tiles_v2_D5all wj495073_2092_2054 $J/j495073_2092_2054_D5_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN55_DONE $(date)"
