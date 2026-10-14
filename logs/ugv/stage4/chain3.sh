#!/usr/bin/env bash
# chain2 보완: 곡선 위 중단(판정 고침)·정지 명령 실패(먼 목표)·교차로(정지까지 기록) + 곡선 보정 작업트리 4대 분리 주행 2회
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
RS=logs/ugv/stage4/run_sc.sh
S=logs/ugv/stage4/single_a_spawn.txt; F=logs/ugv/stage4/single_a_fleet.json
for n in 1 2; do
  bash $RS c3_curve_abort_$n $S $F $PY -m ugv.tools.road_test --tag c3_curve_abort_$n --target 38.0277 128.1303 --abort-after 30 --abort-on-curve 20 --track-s 500 --world kangwon_flat
  bash $RS c3_failstop_$n $S $F $PY -m ugv.tools.road_test --tag c3_failstop_$n --target 38.0277 128.1303 --abort-after 45 --fail-stop-n 1 --track-s 400 --world kangwon_flat
done
bash $RS c3_junction logs/ugv/pair_junction_spawn.txt logs/ugv/pair_junction_fleet.json $PY -m ugv.tools.pair_test run junction --track-s 400
for n in 1 2; do
  bash logs/ugv/stage4/run_sc_wt.sh c3_head_on_comp_$n logs/ugv/pair_head_on_spawn.txt logs/ugv/pair_head_on_fleet.json $PY -m ugv.tools.pair_test run head_on --track-s 400
done
for n in 1 2; do
  bash logs/ugv/stage4/run_sc_wt.sh c3_separate_comp_$n ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY -m ugv.tools.fleet_test separate --track-s 1800
done
echo CHAIN3_DONE
