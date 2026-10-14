#!/usr/bin/env bash
# 2026-10-12 수정 검증 2 (정체 감지 분리·1 s, 코드 cd86b07 다음 커밋). 구성 chain43 과 같음
# 문제 교차로 5곳 × 2회 + 정상 교차로 4곳 × 1회 + 회전 중 취소 회귀 1회. chain42 끝난 뒤 시작
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_fix.sh; ST=$M/logs/ugv/stage5; J=logs/ugv/stage5/jturn
until grep -q CHAIN44_DONE logs/ugv/stage4/chain44.out 2>/dev/null; do sleep 15; done
SUB=$ST/tiles_v2/road_subset_all_included.json
run() {  # tag tiles world spawn fleet rid inst target extra
  PF_SKIP_SUBSET=1 UGV_PX4_PASS_SKIP=1 UGV_OFFROAD_STOP=emergency SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $4 $5 bash -c "cd ../ADAIR_wt_fix && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 60 --world $3 $9"
}
run c45_j494846_1237_1921_fix_a tiles_v2 wj494846_1237_1921 $J/j494846_1237_1921_v2_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0 ""
run c45_j494846_1237_1921_fix_b tiles_v2 wj494846_1237_1921 $J/j494846_1237_1921_v2_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0 ""
run c45_j494943_1351_1352_fix_a tiles_v2 wj494943_1351_1352 $J/j494943_1351_1352_v2_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0 ""
run c45_j494943_1351_1352_fix_b tiles_v2 wj494943_1351_1352 $J/j494943_1351_1352_v2_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0 ""
run c45_j495073_2092_2054_fix_a tiles_v2 wj495073_2092_2054 $J/j495073_2092_2054_v2_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0 ""
run c45_j495073_2092_2054_fix_b tiles_v2 wj495073_2092_2054 $J/j495073_2092_2054_v2_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0 ""
run c45_j494866_0722_1925_fix_a tiles_v2 wj494866_0722_1925 $J/j494866_0722_1925_v2_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6 ""
run c45_j494866_0722_1925_fix_b tiles_v2 wj494866_0722_1925 $J/j494866_0722_1925_v2_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6 ""
run c45_j495759_0730_0731_fix_a tiles_v2 wj495759_0730_0731 $J/j495759_0730_0731_v2_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9 ""
run c45_j495759_0730_0731_fix_b tiles_v2 wj495759_0730_0731 $J/j495759_0730_0731_v2_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9 ""
run c45_j495069_2784_2074_fix_ctl tiles_v2 wj495069_2784_2074 $J/j495069_2784_2074_v2_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1 ""
run c45_j622566_3123_3108_fix_ctl tiles_v2 wj622566_3123_3108 $J/j622566_3123_3108_v2_spawn.txt $J/j622566_3123_3108_fleet.json A-ugv1 1 RP:682503108:61.0 ""
run c45_j494873_0793_1375_fix_ctl tiles_v2 wj494873_0793_1375 $J/j494873_0793_1375_v2_spawn.txt $J/j494873_0793_1375_fleet.json A-ugv1 1 RP:682501375:20.0 ""
run c45_j494990_1573_1574_fix_ctl tiles_v2 wj494990_1573_1574 $J/j494990_1573_1574_v2_spawn.txt $J/j494990_1573_1574_fleet.json A-ugv1 1 RP:682501574:29.1 ""
run c45_j495069_2784_2074_fix_abort tiles_v2 wj495069_2784_2074 $J/j495069_2784_2074_v2_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1 "--abort-after 8"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN45_DONE $(date)"
