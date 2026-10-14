#!/usr/bin/env bash
# 3단계 A 평탄 월드 대표 시험 (간격·정지 수정 d784775 뒤). 출력 logs/ugv/stage4/c2_*
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
RS=logs/ugv/stage4/run_sc.sh
for n in 1 2; do
  bash $RS c2_block_$n logs/ugv/pair_block_spawn.txt logs/ugv/pair_block_fleet.json $PY -m ugv.tools.pair_test run block --track-s 400 --after-s 40
  bash $RS c2_static_ahead_$n logs/ugv/pair_static_ahead_spawn.txt logs/ugv/pair_static_ahead_fleet.json $PY -m ugv.tools.pair_test run static_ahead --track-s 300 --after-s 30
  bash $RS c2_linkloss_$n logs/ugv/pair_linkloss_approach_spawn.txt logs/ugv/pair_linkloss_approach_fleet.json $PY -m ugv.tools.pair_test run linkloss_approach --track-s 300 --after-s 60
done
S=logs/ugv/stage4/single_a_spawn.txt; F=logs/ugv/stage4/single_a_fleet.json
for n in 1 2; do
  bash $RS c2_newtarget_$n $S $F $PY -m ugv.tools.road_test --tag c2_newtarget_$n --target 38.0277 128.1303 --second 38.07515 128.18647 --second-after 25 --second-near-junction 25 --track-s 1500 --world kangwon_flat
  bash $RS c2_curve_abort_$n $S $F $PY -m ugv.tools.road_test --tag c2_curve_abort_$n --target 38.0277 128.1303 --abort-after 30 --abort-on-curve 25 --track-s 500 --world kangwon_flat
  bash $RS c2_failstop_$n $S $F $PY -m ugv.tools.road_test --tag c2_failstop_$n --target-node RP:682501660:46.0 --abort-after 50 --fail-stop-n 1 --track-s 400 --world kangwon_flat
done
for sc in junction head_on; do
  bash $RS c2_$sc logs/ugv/pair_${sc}_spawn.txt logs/ugv/pair_${sc}_fleet.json $PY -m ugv.tools.pair_test run $sc --track-s 400
done
bash $RS c2_separate ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY -m ugv.tools.fleet_test separate --track-s 1800
echo CHAIN2_DONE
