#!/usr/bin/env bash
# 2026-10-12 D 후보 반복·보완 (지시: 2회=초기 선별, 3회 이상, 대조 495069 terrain, 494866 전이 바깥 진입 75 m). 코드·미션·초기 조건 = c41~c46 (wt_turn 30457e7)
# 출발 = 진입 도로 교차로 45 m 앞, 목표 = 진출 도로 20 m 뒤. 사례 = logs/ugv/stage5/jturn/cases.json (make_cases.py)
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh; ST=$M/logs/ugv/stage5; J=logs/ugv/stage5/jturn
SUB=$ST/tiles_v2/road_subset_all_included.json
run() {  # tag tiles world spawn fleet rid inst target
  PF_SKIP_SUBSET=1 UGV_PX4_PASS_SKIP=0 SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $4 $5 bash -c "cd ../ADAIR_wt_turn && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 60 --world $3"
}
run c47_j494943_1351_1352_D_c tiles_v2_D wj494943_1351_1352 $J/j494943_1351_1352_D_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c47_j494866_0722_1925_D_c tiles_v2_D wj494866_0722_1925 $J/j494866_0722_1925_D_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c47_j495069_2784_2074_D_c tiles_v2_D wj495069_2784_2074 $J/j495069_2784_2074_D_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1
run c47_j495069_2784_2074_jt_a tiles_v2_jt_495069 wj495069_2784_2074 $J/j495069_2784_2074_v2_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1
run c47_j495069_2784_2074_jt_b tiles_v2_jt_495069 wj495069_2784_2074 $J/j495069_2784_2074_v2_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1
run c47_j495069_2784_2074_jt_c tiles_v2_jt_495069 wj495069_2784_2074 $J/j495069_2784_2074_v2_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1
run c47_j494866f_v2_a tiles_v2 wj494866_0722_1925 $J/j494866f_0722_1925_v2_spawn.txt $J/j494866f_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c47_j494866f_v2_b tiles_v2 wj494866_0722_1925 $J/j494866f_0722_1925_v2_spawn.txt $J/j494866f_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c47_j494866f_v2_c tiles_v2 wj494866_0722_1925 $J/j494866f_0722_1925_v2_spawn.txt $J/j494866f_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c47_j494866f_jt_a tiles_v2_jt_494866 wj494866_0722_1925 $J/j494866f_0722_1925_jt_spawn.txt $J/j494866f_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c47_j494866f_jt_b tiles_v2_jt_494866 wj494866_0722_1925 $J/j494866f_0722_1925_jt_spawn.txt $J/j494866f_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c47_j494866f_jt_c tiles_v2_jt_494866 wj494866_0722_1925 $J/j494866f_0722_1925_jt_spawn.txt $J/j494866f_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c47_j494866f_D_a tiles_v2_D wj494866_0722_1925 $J/j494866f_0722_1925_D_spawn.txt $J/j494866f_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c47_j494866f_D_b tiles_v2_D wj494866_0722_1925 $J/j494866f_0722_1925_D_spawn.txt $J/j494866f_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c47_j494866f_D_c tiles_v2_D wj494866_0722_1925 $J/j494866f_0722_1925_D_spawn.txt $J/j494866f_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN47_DONE $(date)"
