#!/usr/bin/env bash
# 3단계 보강: 같은 방향 가까이 따라가기 2회 (평탄 A, 작업트리 코드)
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
for n in 1 2; do
  bash logs/ugv/stage4/run_sc_wt.sh c13_follow_close_$n logs/ugv/pair_follow_close_spawn.txt logs/ugv/pair_follow_close_fleet.json $PY -m ugv.tools.pair_test run follow_close --track-s 300 --after-s 10
done
echo CHAIN13_DONE
