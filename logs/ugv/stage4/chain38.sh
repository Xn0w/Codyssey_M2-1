#!/usr/bin/env bash
# 2026-10-12 이어서: (1) 상자 지면 vs 높이장 지면 — 평탄 높이장 월드 fh_bst (B 미션 같음)
#                    (2) 주행 중 지나침 감시(UGV_PX4_PASS_SKIP=1) 켠 재시험 — 실패가 재현된 조건 그대로 (v2, B 1.5·1.0, A 1.0)
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh; ST=$M/logs/ugv/stage5
until grep -q CHAIN37_DONE logs/ugv/stage4/chain37.out 2>/dev/null; do sleep 15; done
BSUB=$ST/tiles_v2_st/road_subset_tc_bst.json; ASUB=$ST/tiles_v2/road_subset_tz_a33v2.json
runb() {  # tag tiles world spawn lat flatz skip pfskip
  PF_SKIP_SUBSET=$8 UGV_PX4_PASS_SKIP=$7 SUBSET=$BSUB EXTRA=stations FLAT_Z=$6 TILES=$2 WORLD=$3 UGV_LAT_ACCEL=$5 bash $RT $1 $4 logs/ugv/stage4/single_b_fleet.json bash -c "cd ../ADAIR_wt_turn && env UGV_LAT_ACCEL=$5 UGV_ROAD_SUBSET=$BSUB UGV_EXTRA_ROADS=$ST/turn/stations_extra_roads.json ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid B-ugv1 --model adair_ugv_3 --target-node RP:683400483:14.7 --abort-after 60 --track-s 120 --world $3"
}
runa() {
  UGV_PX4_PASS_SKIP=$7 SUBSET=$ASUB FLAT_Z=$6 TILES=$2 WORLD=$3 UGV_LAT_ACCEL=$5 bash $RT $1 $4 logs/ugv/stage4/single_a_fleet.json bash -c "cd ../ADAIR_wt_turn && env UGV_LAT_ACCEL=$5 UGV_ROAD_SUBSET=$ASUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid A-ugv1 --model adair_ugv_1 --target-node RP:682501336:293.4 --abort-after 110 --track-s 170 --world $3"
}
runb c38_b_flathm_l15  tiles_flathm fh_bst logs/ugv/stage4/tz_b33v2_spawn_ugv.txt 1.5 "" 0 1
runb c38_b_v2_l15_skip tiles_v2_st  tc_bst logs/ugv/stage4/tz_b33v2_spawn_ugv.txt 1.5 "" 1 0
runb c38_b_v2_l10_skip tiles_v2_st  tc_bst logs/ugv/stage4/tz_b33v2_spawn_ugv.txt 1.0 "" 1 0
runa c38_a_v2_l10_skip tiles_v2     tz_a33v2 logs/ugv/stage4/tz_a33v2_spawn_ugv.txt 1.0 "" 1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN38_DONE $(date)"
