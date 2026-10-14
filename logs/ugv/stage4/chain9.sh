#!/usr/bin/env bash
# 4단계 총괄 통신 단절 실제 벽시계 재시험 (첫 시험은 감시 스크립트 연결 끊김 오류로 300 s 에 멈춤)
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
S=logs/ugv/stage4/single_a_spawn.txt; F=logs/ugv/stage4/single_a_fleet.json
PYTHONFAULTHANDLER=1 bash logs/ugv/stage4/run_sc_wt.sh c9_comm_loss $S $F $PY logs/ugv/stage4/comm_loss_wall.py --rid A-ugv1 --target 37.9650816 128.3175278 --track-s 3900
echo CHAIN9_DONE
# 6단계 커버리지 순회 (지속 운용 chain6 전에)
bash logs/ugv/stage4/chain10.sh > logs/ugv/stage4/chain10.out 2>&1
