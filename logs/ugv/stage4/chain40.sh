#!/usr/bin/env bash
# 2026-10-12 교차로 평탄화 원인 확인: 실패 곡선 교차로 노드 하나만 terrain 혼합(기존 노드별 규칙, ADAIR_JUNC_TERRAIN_NODES)으로 바꾼 타일 — 감시 끔, 다른 조건 c37 과 같음
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh; ST=$M/logs/ugv/stage5
until grep -q CHAIN39_DONE logs/ugv/stage4/chain39.out 2>/dev/null; do sleep 15; done
BSUB=$ST/tiles_v2_st/road_subset_tc_bst.json; ASUB=$ST/tiles_v2/road_subset_tz_a33v2.json
runb() {  # tag tiles world spawn lat flatz skip pfskip
  PF_SKIP_SUBSET=$8 UGV_PX4_PASS_SKIP=$7 SUBSET=$BSUB EXTRA=stations FLAT_Z=$6 TILES=$2 WORLD=$3 UGV_LAT_ACCEL=$5 bash $RT $1 $4 logs/ugv/stage4/single_b_fleet.json bash -c "cd ../ADAIR_wt_turn && env UGV_LAT_ACCEL=$5 UGV_ROAD_SUBSET=$BSUB UGV_EXTRA_ROADS=$ST/turn/stations_extra_roads.json ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid B-ugv1 --model adair_ugv_3 --target-node RP:683400483:14.7 --abort-after 60 --track-s 120 --world $3"
}
runa() {
  UGV_PX4_PASS_SKIP=$7 SUBSET=$ASUB FLAT_Z=$6 TILES=$2 WORLD=$3 UGV_LAT_ACCEL=$5 bash $RT $1 $4 logs/ugv/stage4/single_a_fleet.json bash -c "cd ../ADAIR_wt_turn && env UGV_LAT_ACCEL=$5 UGV_ROAD_SUBSET=$ASUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid A-ugv1 --model adair_ugv_1 --target-node RP:682501336:293.4 --abort-after 110 --track-s 170 --world $3"
}
runb c40_b_jt_l15 tiles_v2_stjt tc_bst logs/ugv/stage4/tz_b33v2_spawn_ugv.txt 1.5 "" 0 0
runa c40_a_jt_l10 tiles_v2_jtA tz_a33v2 logs/ugv/stage4/tz_a33v2_spawn_ugv.txt 1.0 "" 0
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN40_DONE $(date)"
