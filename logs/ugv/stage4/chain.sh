#!/usr/bin/env bash
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
for sc in turn_naerin_ugv turn_naerin_fire turn_deoksan_ugv turn_deoksan_fire turn_deoksan101_ugv; do
  bash logs/ugv/stage4/run_sc.sh $sc logs/ugv/pair_${sc}_spawn.txt logs/ugv/pair_${sc}_fleet.json $PY -m ugv.tools.pair_test run $sc --track-s 240 --after-s 10
done
bash logs/ugv/stage4/run_sc.sh pair_block logs/ugv/pair_block_spawn.txt logs/ugv/pair_block_fleet.json $PY -m ugv.tools.pair_test run block --track-s 400 --after-s 40
for sc in junction head_on; do
  bash logs/ugv/stage4/run_sc.sh pair_$sc logs/ugv/pair_${sc}_spawn.txt logs/ugv/pair_${sc}_fleet.json $PY -m ugv.tools.pair_test run $sc --track-s 400
done
bash logs/ugv/stage4/run_sc.sh fault_block ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY -m ugv.tools.fleet_test fault_block --track-s 900
bash logs/ugv/stage4/run_sc.sh separate ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY -m ugv.tools.fleet_test separate --track-s 1800
echo CHAIN_DONE
