#!/usr/bin/env bash
# 2026-10-12 3단계: 전체 도로망 D5(지형 추종 중심면 설계 교차로, wt_d 1540158) 문제 7곳 × 3회 + 정상 대조 9곳 × 1회. 코드·미션·출발 XY·방향 = c41~c49 (wt_turn 30457e7)
# 출발 = 진입 도로 교차로 45 m 앞, 목표 = 진출 도로 20 m 뒤. 사례 = logs/ugv/stage5/jturn/cases.json (make_cases.py)
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh; ST=$M/logs/ugv/stage5; J=logs/ugv/stage5/jturn
SUB=$ST/tiles_v2/road_subset_all_included.json
run() {  # tag tiles world spawn fleet rid inst target
  PF_SKIP_SUBSET=1 UGV_PX4_PASS_SKIP=0 SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $4 $5 bash -c "cd ../ADAIR_wt_turn && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 60 --world $3"
}
run c51_j494846_1237_1921_D5_a tiles_v2_D5all wj494846_1237_1921 $J/j494846_1237_1921_D5_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run c51_j494846_1237_1921_D5_b tiles_v2_D5all wj494846_1237_1921 $J/j494846_1237_1921_D5_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run c51_j494846_1237_1921_D5_c tiles_v2_D5all wj494846_1237_1921 $J/j494846_1237_1921_D5_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run c51_j495759_0730_0731_D5_a tiles_v2_D5all wj495759_0730_0731 $J/j495759_0730_0731_D5_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c51_j495759_0730_0731_D5_b tiles_v2_D5all wj495759_0730_0731 $J/j495759_0730_0731_D5_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c51_j495759_0730_0731_D5_c tiles_v2_D5all wj495759_0730_0731 $J/j495759_0730_0731_D5_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c51_j494866_0722_1925_D5_a tiles_v2_D5all wj494866_0722_1925 $J/j494866_0722_1925_D5_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c51_j494866_0722_1925_D5_b tiles_v2_D5all wj494866_0722_1925 $J/j494866_0722_1925_D5_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c51_j494866_0722_1925_D5_c tiles_v2_D5all wj494866_0722_1925 $J/j494866_0722_1925_D5_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c51_j495039_2958_3115_D5_a tiles_v2_D5all wj495039_2958_3115 $J/j495039_2958_3115_D5_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
run c51_j495039_2958_3115_D5_b tiles_v2_D5all wj495039_2958_3115 $J/j495039_2958_3115_D5_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
run c51_j495039_2958_3115_D5_c tiles_v2_D5all wj495039_2958_3115 $J/j495039_2958_3115_D5_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
run c51_j494943_1351_1352_D5_a tiles_v2_D5all wj494943_1351_1352 $J/j494943_1351_1352_D5_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c51_j494943_1351_1352_D5_b tiles_v2_D5all wj494943_1351_1352 $J/j494943_1351_1352_D5_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c51_j494943_1351_1352_D5_c tiles_v2_D5all wj494943_1351_1352 $J/j494943_1351_1352_D5_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c51_j495731_0574_0583_D5_a tiles_v2_D5all wj495731_0574_0583 $J/j495731_0574_0583_D5_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run c51_j495731_0574_0583_D5_b tiles_v2_D5all wj495731_0574_0583 $J/j495731_0574_0583_D5_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run c51_j495731_0574_0583_D5_c tiles_v2_D5all wj495731_0574_0583 $J/j495731_0574_0583_D5_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run c51_j495073_2092_2054_D5_a tiles_v2_D5all wj495073_2092_2054 $J/j495073_2092_2054_D5_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run c51_j495073_2092_2054_D5_b tiles_v2_D5all wj495073_2092_2054 $J/j495073_2092_2054_D5_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run c51_j495073_2092_2054_D5_c tiles_v2_D5all wj495073_2092_2054 $J/j495073_2092_2054_D5_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run c51_j496345_0188_0778_D5_ctl tiles_v2_D5all wj496345_0188_0778 $J/j496345_0188_0778_D5_spawn.txt $J/j496345_0188_0778_fleet.json B-ugv1 3 RP:684400778:175.9
run c51_j494990_1573_1574_D5_ctl tiles_v2_D5all wj494990_1573_1574 $J/j494990_1573_1574_D5_spawn.txt $J/j494990_1573_1574_fleet.json A-ugv1 1 RP:682501574:29.1
run c51_j495663_1400_0021_D5_ctl tiles_v2_D5all wj495663_1400_0021 $J/j495663_1400_0021_D5_spawn.txt $J/j495663_1400_0021_fleet.json B-ugv1 3 RP:683400021:20.0
run c51_j494865_0523_1574_D5_ctl tiles_v2_D5all wj494865_0523_1574 $J/j494865_0523_1574_D5_spawn.txt $J/j494865_0523_1574_fleet.json A-ugv1 1 RP:682501574:20.0
run c51_j495794_0381_0383_D5_ctl tiles_v2_D5all wj495794_0381_0383 $J/j495794_0381_0383_D5_spawn.txt $J/j495794_0381_0383_fleet.json B-ugv1 3 RP:683500383:94.1
run c51_j495069_2784_2074_D5_ctl tiles_v2_D5all wj495069_2784_2074 $J/j495069_2784_2074_D5_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1
run c51_j494873_0793_1375_D5_ctl tiles_v2_D5all wj494873_0793_1375 $J/j494873_0793_1375_D5_spawn.txt $J/j494873_0793_1375_fleet.json A-ugv1 1 RP:682501375:20.0
run c51_j495011_1875_1652_D5_ctl tiles_v2_D5all wj495011_1875_1652 $J/j495011_1875_1652_D5_spawn.txt $J/j495011_1875_1652_fleet.json A-ugv1 1 RP:682501652:43.0
run c51_j622566_3123_3108_D5_ctl tiles_v2_D5all wj622566_3123_3108 $J/j622566_3123_3108_D5_spawn.txt $J/j622566_3123_3108_fleet.json A-ugv1 1 RP:682503108:61.0
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN51_DONE $(date)"
