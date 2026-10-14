#!/usr/bin/env bash
# 2026-10-12 D5 반복 확인: 새 불합격 j495663, 경계 민감 j495759·j495731 각 3회, 같은 지면·서버(wt_turn 30457e7). 시험 도구만 wt_fix road_test(--post-stop-s 15, 관측 전용)
# 출발 = 진입 도로 교차로 45 m 앞, 목표 = 진출 도로 20 m 뒤. 사례 = logs/ugv/stage5/jturn/cases.json (make_cases.py)
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh; ST=$M/logs/ugv/stage5; J=logs/ugv/stage5/jturn
SUB=$ST/tiles_v2/road_subset_all_included.json
run() {  # tag tiles world spawn fleet rid inst target  — 서버 wt_turn, 시험 도구(관측) wt_fix
  PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $4 $5 bash -c "cd ../ADAIR_wt_fix && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 120 --post-stop-s 15 --world $3"
}
run c52_j495663_1400_0021_D5_a tiles_v2_D5all wj495663_1400_0021 $J/j495663_1400_0021_D5_spawn.txt $J/j495663_1400_0021_fleet.json B-ugv1 3 RP:683400021:20.0
run c52_j495663_1400_0021_D5_b tiles_v2_D5all wj495663_1400_0021 $J/j495663_1400_0021_D5_spawn.txt $J/j495663_1400_0021_fleet.json B-ugv1 3 RP:683400021:20.0
run c52_j495663_1400_0021_D5_c tiles_v2_D5all wj495663_1400_0021 $J/j495663_1400_0021_D5_spawn.txt $J/j495663_1400_0021_fleet.json B-ugv1 3 RP:683400021:20.0
run c52_j495759_0730_0731_D5_a tiles_v2_D5all wj495759_0730_0731 $J/j495759_0730_0731_D5_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c52_j495759_0730_0731_D5_b tiles_v2_D5all wj495759_0730_0731 $J/j495759_0730_0731_D5_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c52_j495759_0730_0731_D5_c tiles_v2_D5all wj495759_0730_0731 $J/j495759_0730_0731_D5_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run c52_j495731_0574_0583_D5_a tiles_v2_D5all wj495731_0574_0583 $J/j495731_0574_0583_D5_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run c52_j495731_0574_0583_D5_b tiles_v2_D5all wj495731_0574_0583 $J/j495731_0574_0583_D5_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run c52_j495731_0574_0583_D5_c tiles_v2_D5all wj495731_0574_0583 $J/j495731_0574_0583_D5_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN52_DONE $(date)"
