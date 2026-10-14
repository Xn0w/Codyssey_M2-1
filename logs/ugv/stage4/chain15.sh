#!/usr/bin/env bash
# 3번 검증 (acd404f: 추종 여유·정지 경로 속도 상한): 평탄 월드 4대 출동·복귀 ×2 (교차로 전이 이탈 재확인) + 정지 재확인 (고장·취소)
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
RW=logs/ugv/stage4/run_sc_wt.sh
for n in 1 2; do
  bash $RW c15_separate_$n ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY -m ugv.tools.fleet_test separate --track-s 1800
done
bash $RW c15_stopv logs/ugv/stage4/pair_a_spawn.txt logs/ugv/stage4/pair_a_fleet.json $PY logs/ugv/stage4/stop_verify.py --scenarios fault,abort
echo CHAIN15_DONE
