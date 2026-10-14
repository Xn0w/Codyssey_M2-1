#!/usr/bin/env bash
# 2026-10-11 회전 공터 시험 (사용자 요청): 시험 월드 tz_b33t = tz_b33 + 683400613 양끝 시험 전용 회전 공터(풍선 고리 R 9 m, 15°).
# 코드 = ../ADAIR_wt_turn (c29 뒤 수정: 계획 중 지난 지점 빼기·진행 방위·정지 경로 예측을 경로 진행 위치로 — 같은 자리 재통과 경로).
# 목표 RP:683400613:171.1 (막다른 끝 495733 앞 19 m) — 오르막 평균 10.8 %·2 m 최대 16.6 % 올라 도착, 60 s 정차, 복귀 = 끝 회전 공터 돌아 내리막.
cd "$(dirname "$0")/../../.."
M=$(pwd)
PY=$M/.venv/Scripts/python.exe
RT=logs/ugv/stage4/run_sc_turn.sh
export WORLD=tz_b33t EXTRA=tz_b33t
TGT=RP:683400613:171.1
ENVX="UGV_EXTRA_ROADS=$M/logs/ugv/stage5/turn/tz_b33t_extra_roads.json UGV_ROAD_SUBSET=$M/logs/ugv/stage5/tiles_turn/road_subset_tz_b33t.json ADAIR_TILES_OUT=$M/logs/ugv/stage5/tiles_turn"
bash $RT c30_turn_ugv logs/ugv/stage4/tz_b33_spawn_ugv.txt logs/ugv/stage4/single_b_fleet.json bash -c "cd ../ADAIR_wt_turn && env $ENVX $PY -m ugv.tools.road_test --tag c30_turn_ugv --rid B-ugv1 --model adair_ugv_3 --target-node $TGT --dwell-s 60 --return-home --track-s 600 --world tz_b33t"
bash $RT c30_turn_fire logs/ugv/stage4/tz_b33_spawn_fire.txt logs/ugv/stage4/single_bfire_fleet.json bash -c "cd ../ADAIR_wt_turn && env $ENVX $PY -m ugv.tools.road_test --tag c30_turn_fire --rid B-fire1 --model adair_firetruck_4 --target-node $TGT --dwell-s 60 --return-home --track-s 600 --world tz_b33t"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN30_DONE $(date)"
cd ../ADAIR_wt_turn && PYTHONIOENCODING=utf-8 $PY -m pytest -q -p no:cacheprovider ugv/tests orchestrator/tests tests/test_uav_requests.py > $M/logs/ugv/stage4/c30_pytest.out 2>&1; tail -3 $M/logs/ugv/stage4/c30_pytest.out
echo "CHAIN30_PYTEST_DONE $(date)"
