#!/usr/bin/env bash
# 2026-10-12 서스펜션 차량 모델 사본(susp, fable_make_susp.py: 바퀴별 수직 prismatic K 130 kN/m C 8 kN·s/m ±10 cm, 구동·조향·마찰 동일) 검증.
# 페이블 원인 확정: 무서스펜션 강체 → 대각 두 바퀴만 하중 → 회전 응답 부족 → 경유점 놓침. 494943 susp D8·D5 합격 1회씩.
# 교차로 16곳(문제 7 + 정상 대조 9) × 지면 D8·v2 × 1회. 서버 wt_turn 30457e7, 시험 도구 wt_fix, PASS_SKIP=0 STALL_DETECT=0, track-s 120, post-stop 15, LAT_ACCEL 1.0
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh; ST=$M/logs/ugv/stage5; J=logs/ugv/stage5/jturn
SUB=$ST/tiles_v2/road_subset_all_included.json
export GZ_MODEL_OVERRIDE=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/logs/ugv/stage5/jturn/fable_models/susp
run() {
  UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=0 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $4 $5 bash -c "cd ../ADAIR_wt_fix && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 120 --post-stop-s 15 --world $3"
}
run c56_j494846_1237_1921_D8_susp tiles_v2_D8all wj494846_1237_1921 $J/j494846_1237_1921_D8_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run c56_j495759_0730_0731_D8_susp tiles_v2_D8all wj495759_0730_0731 $J/j495759_0730_0731_D8_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c56_j494866_0722_1925_D8_susp tiles_v2_D8all wj494866_0722_1925 $J/j494866_0722_1925_D8_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c56_j495039_2958_3115_D8_susp tiles_v2_D8all wj495039_2958_3115 $J/j495039_2958_3115_D8_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
run c56_j494943_1351_1352_D8_susp tiles_v2_D8all wj494943_1351_1352 $J/j494943_1351_1352_D8_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c56_j495731_0574_0583_D8_susp tiles_v2_D8all wj495731_0574_0583 $J/j495731_0574_0583_D8_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run c56_j495073_2092_2054_D8_susp tiles_v2_D8all wj495073_2092_2054 $J/j495073_2092_2054_D8_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run c56_j496345_0188_0778_D8_susp tiles_v2_D8all wj496345_0188_0778 $J/j496345_0188_0778_D8_spawn.txt $J/j496345_0188_0778_fleet.json B-ugv1 3 RP:684400778:175.9
run c56_j494990_1573_1574_D8_susp tiles_v2_D8all wj494990_1573_1574 $J/j494990_1573_1574_D8_spawn.txt $J/j494990_1573_1574_fleet.json A-ugv1 1 RP:682501574:29.1
run c56_j495663_1400_0021_D8_susp tiles_v2_D8all wj495663_1400_0021 $J/j495663_1400_0021_D8_spawn.txt $J/j495663_1400_0021_fleet.json B-ugv1 3 RP:683400021:20.0
run c56_j494865_0523_1574_D8_susp tiles_v2_D8all wj494865_0523_1574 $J/j494865_0523_1574_D8_spawn.txt $J/j494865_0523_1574_fleet.json A-ugv1 1 RP:682501574:20.0
run c56_j495794_0381_0383_D8_susp tiles_v2_D8all wj495794_0381_0383 $J/j495794_0381_0383_D8_spawn.txt $J/j495794_0381_0383_fleet.json B-ugv1 3 RP:683500383:94.1
run c56_j495069_2784_2074_D8_susp tiles_v2_D8all wj495069_2784_2074 $J/j495069_2784_2074_D8_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1
run c56_j494873_0793_1375_D8_susp tiles_v2_D8all wj494873_0793_1375 $J/j494873_0793_1375_D8_spawn.txt $J/j494873_0793_1375_fleet.json A-ugv1 1 RP:682501375:20.0
run c56_j495011_1875_1652_D8_susp tiles_v2_D8all wj495011_1875_1652 $J/j495011_1875_1652_D8_spawn.txt $J/j495011_1875_1652_fleet.json A-ugv1 1 RP:682501652:43.0
run c56_j622566_3123_3108_D8_susp tiles_v2_D8all wj622566_3123_3108 $J/j622566_3123_3108_D8_spawn.txt $J/j622566_3123_3108_fleet.json A-ugv1 1 RP:682503108:61.0
run c56_j494846_1237_1921_v2_susp tiles_v2 wj494846_1237_1921 $J/j494846_1237_1921_v2_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run c56_j495759_0730_0731_v2_susp tiles_v2 wj495759_0730_0731 $J/j495759_0730_0731_v2_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c56_j494866_0722_1925_v2_susp tiles_v2 wj494866_0722_1925 $J/j494866_0722_1925_v2_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run c56_j495039_2958_3115_v2_susp tiles_v2 wj495039_2958_3115 $J/j495039_2958_3115_v2_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
run c56_j494943_1351_1352_v2_susp tiles_v2 wj494943_1351_1352 $J/j494943_1351_1352_v2_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c56_j495731_0574_0583_v2_susp tiles_v2 wj495731_0574_0583 $J/j495731_0574_0583_v2_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run c56_j495073_2092_2054_v2_susp tiles_v2 wj495073_2092_2054 $J/j495073_2092_2054_v2_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run c56_j496345_0188_0778_v2_susp tiles_v2 wj496345_0188_0778 $J/j496345_0188_0778_v2_spawn.txt $J/j496345_0188_0778_fleet.json B-ugv1 3 RP:684400778:175.9
run c56_j494990_1573_1574_v2_susp tiles_v2 wj494990_1573_1574 $J/j494990_1573_1574_v2_spawn.txt $J/j494990_1573_1574_fleet.json A-ugv1 1 RP:682501574:29.1
run c56_j495663_1400_0021_v2_susp tiles_v2 wj495663_1400_0021 $J/j495663_1400_0021_v2_spawn.txt $J/j495663_1400_0021_fleet.json B-ugv1 3 RP:683400021:20.0
run c56_j494865_0523_1574_v2_susp tiles_v2 wj494865_0523_1574 $J/j494865_0523_1574_v2_spawn.txt $J/j494865_0523_1574_fleet.json A-ugv1 1 RP:682501574:20.0
run c56_j495794_0381_0383_v2_susp tiles_v2 wj495794_0381_0383 $J/j495794_0381_0383_v2_spawn.txt $J/j495794_0381_0383_fleet.json B-ugv1 3 RP:683500383:94.1
run c56_j495069_2784_2074_v2_susp tiles_v2 wj495069_2784_2074 $J/j495069_2784_2074_v2_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1
run c56_j494873_0793_1375_v2_susp tiles_v2 wj494873_0793_1375 $J/j494873_0793_1375_v2_spawn.txt $J/j494873_0793_1375_fleet.json A-ugv1 1 RP:682501375:20.0
run c56_j495011_1875_1652_v2_susp tiles_v2 wj495011_1875_1652 $J/j495011_1875_1652_v2_spawn.txt $J/j495011_1875_1652_fleet.json A-ugv1 1 RP:682501652:43.0
run c56_j622566_3123_3108_v2_susp tiles_v2 wj622566_3123_3108 $J/j622566_3123_3108_v2_spawn.txt $J/j622566_3123_3108_fleet.json A-ugv1 1 RP:682503108:61.0
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN56_DONE $(date)"
