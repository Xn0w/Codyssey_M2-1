#!/usr/bin/env bash
# 2026-10-12 이탈 원인 비교시험 (조건 고정, 한 번에 하나만 변경): 같은 도로 부분집합(=같은 계획)·같은 생성 위치·방위·PX4 설정·차량.
# 바꾸는 것: 지면(v2 / v1 / 평탄) 또는 횡가속(곡선 속도). 미션은 이탈 지점을 지난 뒤 중단(--abort-after), 복귀 없음.
# B: c36 과 같은 조건(횡가속 1.5 기본값). A: c33_v2_bridge 와 같은 조건(횡가속 1.0).
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh; ST=$M/logs/ugv/stage5
BSUB=$ST/tiles_v2_st/road_subset_tc_bst.json; ASUB=$ST/tiles_v2/road_subset_tz_a33v2.json
runb() {  # tag tiles world spawn lat flatz
  SUBSET=$BSUB EXTRA=stations FLAT_Z=$6 TILES=$2 WORLD=$3 UGV_LAT_ACCEL=$5 bash $RT $1 $4 logs/ugv/stage4/single_b_fleet.json bash -c "cd ../ADAIR_wt_turn && env UGV_LAT_ACCEL=$5 UGV_ROAD_SUBSET=$BSUB UGV_EXTRA_ROADS=$ST/turn/stations_extra_roads.json ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid B-ugv1 --model adair_ugv_3 --target-node RP:683400483:14.7 --abort-after 60 --track-s 120 --world $3"
}
runa() {
  SUBSET=$ASUB FLAT_Z=$6 TILES=$2 WORLD=$3 UGV_LAT_ACCEL=$5 bash $RT $1 $4 logs/ugv/stage4/single_a_fleet.json bash -c "cd ../ADAIR_wt_turn && env UGV_LAT_ACCEL=$5 UGV_ROAD_SUBSET=$ASUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid A-ugv1 --model adair_ugv_1 --target-node RP:682501336:293.4 --abort-after 110 --track-s 170 --world $3"
}
runb c37_b_v2_l15   tiles_v2_st tc_bst logs/ugv/stage4/tz_b33v2_spawn_ugv.txt 1.5 ""
runb c37_b_flat_l15 tiles_flat  fc_bst logs/ugv/stage4/tz_b33v2_spawn_ugv.txt 1.5 126.179
runb c37_b_v1_l15   tiles       tc_bst logs/ugv/stage4/tc_bst_v1_spawn_ugv.txt 1.5 ""
runb c37_b_v2_l10   tiles_v2_st tc_bst logs/ugv/stage4/tz_b33v2_spawn_ugv.txt 1.0 ""
runb c37_b_v2_l06   tiles_v2_st tc_bst logs/ugv/stage4/tz_b33v2_spawn_ugv.txt 0.6 ""
runa c37_a_v2_l10   tiles_v2    tz_a33v2 logs/ugv/stage4/tz_a33v2_spawn_ugv.txt 1.0 ""
runa c37_a_flat_l10 tiles_flat  fa_33  logs/ugv/stage4/tz_a33v2_spawn_ugv.txt 1.0 25.851
runa c37_a_v1_l10   tiles       tz_a33 logs/ugv/stage4/tz_a33_spawn_ugv.txt 1.0 ""
runa c37_a_v2_l06   tiles_v2    tz_a33v2 logs/ugv/stage4/tz_a33v2_spawn_ugv.txt 0.6 ""
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN37_DONE $(date)"
