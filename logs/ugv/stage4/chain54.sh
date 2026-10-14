#!/usr/bin/env bash
# 2026-10-12 감속 비교: 곡선 횡가속 UGV_LAT_ACCEL 0.6 (기준 1.0) — 회전 직후 바깥 밀림(PX4_TRACKING 0.01~0.44 m)이 줄어드는지.
# 지면 D8(tiles_v2_D8all) 실패·경계 교차로 4곳 × 3, v2(tiles_v2) 실패 2곳 × 3, D8 정상 대조 2곳 × 1. 서버 wt_turn 30457e7, 시험 도구 wt_fix(--post-stop-s 15). 기준(1.0)은 chain53·c41~c52 와 비교
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh; ST=$M/logs/ugv/stage5; J=logs/ugv/stage5/jturn
until grep -q CHAIN53_DONE logs/ugv/stage4/chain53.out 2>/dev/null; do sleep 15; done
SUB=$ST/tiles_v2/road_subset_all_included.json
LA=0.6
run() {  # tag tiles world spawn fleet rid inst target
  PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=$LA bash $RT $1 $4 $5 bash -c "cd ../ADAIR_wt_fix && env UGV_LAT_ACCEL=$LA UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 150 --post-stop-s 15 --world $3"
}
for s in a b c; do
run c54_j495759_0730_0731_D8_la06_$s tiles_v2_D8all wj495759_0730_0731 $J/j495759_0730_0731_D8_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c54_j495731_0574_0583_D8_la06_$s tiles_v2_D8all wj495731_0574_0583 $J/j495731_0574_0583_D8_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run c54_j495663_1400_0021_D8_la06_$s tiles_v2_D8all wj495663_1400_0021 $J/j495663_1400_0021_D8_spawn.txt $J/j495663_1400_0021_fleet.json B-ugv1 3 RP:683400021:20.0
run c54_j494846_1237_1921_D8_la06_$s tiles_v2_D8all wj494846_1237_1921 $J/j494846_1237_1921_D8_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run c54_j495759_0730_0731_v2_la06_$s tiles_v2 wj495759_0730_0731 $J/j495759_0730_0731_v2_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c54_j495731_0574_0583_v2_la06_$s tiles_v2 wj495731_0574_0583 $J/j495731_0574_0583_v2_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
done
run c54_j494943_1351_1352_D8_la06_ctl tiles_v2_D8all wj494943_1351_1352 $J/j494943_1351_1352_D8_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run c54_j495073_2092_2054_D8_la06_ctl tiles_v2_D8all wj495073_2092_2054 $J/j495073_2092_2054_D8_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN54_DONE $(date)"
