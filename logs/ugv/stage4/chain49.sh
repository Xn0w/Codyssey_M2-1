#!/usr/bin/env bash
# 2026-10-12 D2(도로별 접속 종단·평면 경사 상한·주도로 판정 수정) 494943·495069 각 3회 + v2 j494943 출발 민감도(옆 ±0.2 m, 방위 ±1°). 코드 = c46 (wt_turn 30457e7)
# 출발 = 진입 도로 교차로 45 m 앞, 목표 = 진출 도로 20 m 뒤. 사례 = logs/ugv/stage5/jturn/cases.json (make_cases.py)
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh; ST=$M/logs/ugv/stage5; J=logs/ugv/stage5/jturn
until grep -q CHAIN48_DONE logs/ugv/stage4/chain48.out 2>/dev/null; do sleep 20; done
SUB=$ST/tiles_v2/road_subset_all_included.json
run() {  # tag tiles world spawn fleet rid inst target
  PF_SKIP_SUBSET=1 UGV_PX4_PASS_SKIP=0 SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $4 $5 bash -c "cd ../ADAIR_wt_turn && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 60 --world $3"
}
run c49_j494943_1351_1352_D2_a tiles_v2_D2 wj494943_1351_1352 $J/j494943_1351_1352_D2_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c49_j494943_1351_1352_D2_b tiles_v2_D2 wj494943_1351_1352 $J/j494943_1351_1352_D2_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c49_j494943_1351_1352_D2_c tiles_v2_D2 wj494943_1351_1352 $J/j494943_1351_1352_D2_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c49_j495069_2784_2074_D2_a tiles_v2_D2 wj495069_2784_2074 $J/j495069_2784_2074_D2_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1
run c49_j495069_2784_2074_D2_b tiles_v2_D2 wj495069_2784_2074 $J/j495069_2784_2074_D2_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1
run c49_j495069_2784_2074_D2_c tiles_v2_D2 wj495069_2784_2074 $J/j495069_2784_2074_D2_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1
run c49_j494943_v2latp tiles_v2 wj494943_1351_1352 $J/j494943_1351_1352_v2latp_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c49_j494943_v2latm tiles_v2 wj494943_1351_1352 $J/j494943_1351_1352_v2latm_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c49_j494943_v2yawp tiles_v2 wj494943_1351_1352 $J/j494943_1351_1352_v2yawp_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c49_j494943_v2yawm tiles_v2 wj494943_1351_1352 $J/j494943_1351_1352_v2yawm_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN49_DONE $(date)"
