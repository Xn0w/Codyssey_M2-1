#!/usr/bin/env bash
# 2026-10-12 교차로 회전 재현성: chain41 에서 v2 가 실패한 7곳을 v2·v1 각 2회 + j495011 v2 2회 (조건 chain41 과 같음)
# 출발 = 진입 도로 교차로 45 m 앞, 목표 = 진출 도로 20 m 뒤. 사례 = logs/ugv/stage5/jturn/cases.json (make_cases.py)
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh; ST=$M/logs/ugv/stage5; J=logs/ugv/stage5/jturn
SUB=$ST/tiles_v2/road_subset_all_included.json
run() {  # tag tiles world spawn fleet rid inst target
  PF_SKIP_SUBSET=1 UGV_PX4_PASS_SKIP=0 SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $4 $5 bash -c "cd ../ADAIR_wt_turn && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 60 --world $3"
}
run c42_j494846_1237_1921_v2_r2 tiles_v2 wj494846_1237_1921 $J/j494846_1237_1921_v2_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run c42_j494846_1237_1921_v1_r2 tiles wj494846_1237_1921 $J/j494846_1237_1921_v1_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run c42_j494846_1237_1921_v2_r3 tiles_v2 wj494846_1237_1921 $J/j494846_1237_1921_v2_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run c42_j494846_1237_1921_v1_r3 tiles wj494846_1237_1921 $J/j494846_1237_1921_v1_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run c42_j495759_0730_0731_v2_r2 tiles_v2 wj495759_0730_0731 $J/j495759_0730_0731_v2_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c42_j495759_0730_0731_v1_r2 tiles wj495759_0730_0731 $J/j495759_0730_0731_v1_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c42_j495759_0730_0731_v2_r3 tiles_v2 wj495759_0730_0731 $J/j495759_0730_0731_v2_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c42_j495759_0730_0731_v1_r3 tiles wj495759_0730_0731 $J/j495759_0730_0731_v1_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c42_j494866_0722_1925_v2_r2 tiles_v2 wj494866_0722_1925 $J/j494866_0722_1925_v2_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c42_j494866_0722_1925_v1_r2 tiles wj494866_0722_1925 $J/j494866_0722_1925_v1_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c42_j494866_0722_1925_v2_r3 tiles_v2 wj494866_0722_1925 $J/j494866_0722_1925_v2_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c42_j494866_0722_1925_v1_r3 tiles wj494866_0722_1925 $J/j494866_0722_1925_v1_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c42_j495039_2958_3115_v2_r2 tiles_v2 wj495039_2958_3115 $J/j495039_2958_3115_v2_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
run c42_j495039_2958_3115_v1_r2 tiles wj495039_2958_3115 $J/j495039_2958_3115_v1_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
run c42_j495039_2958_3115_v2_r3 tiles_v2 wj495039_2958_3115 $J/j495039_2958_3115_v2_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
run c42_j495039_2958_3115_v1_r3 tiles wj495039_2958_3115 $J/j495039_2958_3115_v1_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
run c42_j494943_1351_1352_v2_r2 tiles_v2 wj494943_1351_1352 $J/j494943_1351_1352_v2_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c42_j494943_1351_1352_v1_r2 tiles wj494943_1351_1352 $J/j494943_1351_1352_v1_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c42_j494943_1351_1352_v2_r3 tiles_v2 wj494943_1351_1352 $J/j494943_1351_1352_v2_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c42_j494943_1351_1352_v1_r3 tiles wj494943_1351_1352 $J/j494943_1351_1352_v1_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c42_j495731_0574_0583_v2_r2 tiles_v2 wj495731_0574_0583 $J/j495731_0574_0583_v2_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run c42_j495731_0574_0583_v1_r2 tiles wj495731_0574_0583 $J/j495731_0574_0583_v1_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run c42_j495731_0574_0583_v2_r3 tiles_v2 wj495731_0574_0583 $J/j495731_0574_0583_v2_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run c42_j495731_0574_0583_v1_r3 tiles wj495731_0574_0583 $J/j495731_0574_0583_v1_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run c42_j495073_2092_2054_v2_r2 tiles_v2 wj495073_2092_2054 $J/j495073_2092_2054_v2_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run c42_j495073_2092_2054_v1_r2 tiles wj495073_2092_2054 $J/j495073_2092_2054_v1_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run c42_j495073_2092_2054_v2_r3 tiles_v2 wj495073_2092_2054 $J/j495073_2092_2054_v2_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run c42_j495073_2092_2054_v1_r3 tiles wj495073_2092_2054 $J/j495073_2092_2054_v1_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run c42_j495011_1875_1652_v2_r2 tiles_v2 wj495011_1875_1652 $J/j495011_1875_1652_v2_spawn.txt $J/j495011_1875_1652_fleet.json A-ugv1 1 RP:682501652:43.0
run c42_j495011_1875_1652_v2_r3 tiles_v2 wj495011_1875_1652 $J/j495011_1875_1652_v2_spawn.txt $J/j495011_1875_1652_fleet.json A-ugv1 1 RP:682501652:43.0
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN42_DONE $(date)"
