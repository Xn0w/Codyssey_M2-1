#!/usr/bin/env bash
# 평지 전체 월드 A→B 1회 (기준: logs/ugv/stage4/flat_ab1_criteria.md)
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
M=$(pwd)
FLAT_Z=0 SUBSET=$M/logs/ugv/stage5/tiles_v2/road_subset_all_included.json SERVER_TREE=ADAIR_wt_integ \
  bash logs/ugv/stage4/run_flat_ab.sh flat_ab1_ugv logs/ugv/stage4/single_a_spawn.txt logs/ugv/stage4/single_a_fleet.json \
  $PY -m ugv.tools.road_test --tag flat_ab1_ugv --rid A-ugv1 --model adair_ugv_1 --target-node RP:683400513:2315.4 --track-s 6000 --world kangwon_flat
echo "CHAIN_FLAT_AB1_DONE rc=$?"
