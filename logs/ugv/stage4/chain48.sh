#!/usr/bin/env bash
# 2026-10-12 실행 지시서 1단계 Gazebo: (1) j494846·j495759 노드 단독 terrain 짧은 시험 3회 (c44 와 같은 조건, wt_turn 30457e7)
# (2) c41 무효 2건 재시험 (wt_turn) (3) 정체 감지 ON·건너뛰기 OFF (wt_fix d8cb97c): 문제 4곳 × 일반 직선 정지 2회 + 비상 직선 정지 2회, 정상 대조 4곳 × 1회.
#     임무 끝 뒤 정지 확인 + 15 s 관측(--post-stop-s), 기록 150 s
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; ST=$M/logs/ugv/stage5; J=logs/ugv/stage5/jturn
until ! ps -ef | grep -v grep | grep -q "test_orchestrator_closed_loop"; do sleep 15; done
SUB=$ST/tiles_v2/road_subset_all_included.json
runT() {  # tag tiles world spawn fleet rid inst target   (wt_turn, c41/c44 조건)
  PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash logs/ugv/stage4/run_sc_v2.sh $1 $4 $5 bash -c "cd ../ADAIR_wt_turn && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 60 --world $3"
}
runF() {  # tag tiles world spawn fleet rid inst target stopmode   (wt_fix, 정체 감지 ON, 건너뛰기 OFF)
  PF_SKIP_SUBSET=1 UGV_PX4_STALL_DETECT=1 UGV_PX4_PASS_SKIP=0 UGV_OFFROAD_STOP=$9 SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash logs/ugv/stage4/run_sc_fix.sh $1 $4 $5 bash -c "cd ../ADAIR_wt_fix && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 150 --post-stop-s 15 --world $3"
}
runT c48_j494846_1237_1921_jt_a tiles_v2_jt_494846 wj494846_1237_1921 $J/j494846_1237_1921_v2_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
runT c48_j494846_1237_1921_jt_b tiles_v2_jt_494846 wj494846_1237_1921 $J/j494846_1237_1921_v2_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
runT c48_j494846_1237_1921_jt_c tiles_v2_jt_494846 wj494846_1237_1921 $J/j494846_1237_1921_v2_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
runT c48_j495759_0730_0731_jt_a tiles_v2_jt_495759 wj495759_0730_0731 $J/j495759_0730_0731_v2_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
runT c48_j495759_0730_0731_jt_b tiles_v2_jt_495759 wj495759_0730_0731 $J/j495759_0730_0731_v2_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
runT c48_j495759_0730_0731_jt_c tiles_v2_jt_495759 wj495759_0730_0731 $J/j495759_0730_0731_v2_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
runT c48_j495039_2958_3115_v1_rerun tiles wj495039_2958_3115 $J/j495039_2958_3115_v1_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
runT c48_j495011_1875_1652_v2_rerun tiles_v2 wj495011_1875_1652 $J/j495011_1875_1652_v2_spawn.txt $J/j495011_1875_1652_fleet.json A-ugv1 1 RP:682501652:43.0
runF c48_j494846_1237_1921_stall_stra_a tiles_v2 wj494846_1237_1921 $J/j494846_1237_1921_v2_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0 straight
runF c48_j494846_1237_1921_stall_stra_b tiles_v2 wj494846_1237_1921 $J/j494846_1237_1921_v2_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0 straight
runF c48_j494846_1237_1921_stall_emer_a tiles_v2 wj494846_1237_1921 $J/j494846_1237_1921_v2_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0 emergency
runF c48_j494846_1237_1921_stall_emer_b tiles_v2 wj494846_1237_1921 $J/j494846_1237_1921_v2_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0 emergency
runF c48_j494866_0722_1925_stall_stra_a tiles_v2 wj494866_0722_1925 $J/j494866_0722_1925_v2_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6 straight
runF c48_j494866_0722_1925_stall_stra_b tiles_v2 wj494866_0722_1925 $J/j494866_0722_1925_v2_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6 straight
runF c48_j494866_0722_1925_stall_emer_a tiles_v2 wj494866_0722_1925 $J/j494866_0722_1925_v2_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6 emergency
runF c48_j494866_0722_1925_stall_emer_b tiles_v2 wj494866_0722_1925 $J/j494866_0722_1925_v2_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6 emergency
runF c48_j495073_2092_2054_stall_stra_a tiles_v2 wj495073_2092_2054 $J/j495073_2092_2054_v2_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0 straight
runF c48_j495073_2092_2054_stall_stra_b tiles_v2 wj495073_2092_2054 $J/j495073_2092_2054_v2_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0 straight
runF c48_j495073_2092_2054_stall_emer_a tiles_v2 wj495073_2092_2054 $J/j495073_2092_2054_v2_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0 emergency
runF c48_j495073_2092_2054_stall_emer_b tiles_v2 wj495073_2092_2054 $J/j495073_2092_2054_v2_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0 emergency
runF c48_j494943_1351_1352_stall_stra_a tiles_v2 wj494943_1351_1352 $J/j494943_1351_1352_v2_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0 straight
runF c48_j494943_1351_1352_stall_stra_b tiles_v2 wj494943_1351_1352 $J/j494943_1351_1352_v2_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0 straight
runF c48_j494943_1351_1352_stall_emer_a tiles_v2 wj494943_1351_1352 $J/j494943_1351_1352_v2_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0 emergency
runF c48_j494943_1351_1352_stall_emer_b tiles_v2 wj494943_1351_1352 $J/j494943_1351_1352_v2_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0 emergency
runF c48_j495069_2784_2074_stall_ctl tiles_v2 wj495069_2784_2074 $J/j495069_2784_2074_v2_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1 straight
runF c48_j622566_3123_3108_stall_ctl tiles_v2 wj622566_3123_3108 $J/j622566_3123_3108_v2_spawn.txt $J/j622566_3123_3108_fleet.json A-ugv1 1 RP:682503108:61.0 straight
runF c48_j494873_0793_1375_stall_ctl tiles_v2 wj494873_0793_1375 $J/j494873_0793_1375_v2_spawn.txt $J/j494873_0793_1375_fleet.json A-ugv1 1 RP:682501375:20.0 straight
runF c48_j494990_1573_1574_stall_ctl tiles_v2 wj494990_1573_1574 $J/j494990_1573_1574_v2_spawn.txt $J/j494990_1573_1574_fleet.json A-ugv1 1 RP:682501574:29.1 straight
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN48_DONE $(date)"
