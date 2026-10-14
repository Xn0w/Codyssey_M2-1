#!/usr/bin/env bash
# 6단계 B 거점 주변 지형 구역 (tz_b33, 시험용 구역 — 교량 제외 망에서 B 지역은 전체 강연결 묶음 밖이라 구역 부분집합으로만 배치 가능)
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
RT=logs/ugv/stage4/run_sc_tz.sh
export WORLD=tz_b33
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage5/coverage.py > /dev/null 2>&1
UGV_MAX_SPEED_KMH=30 bash $RT c11_b_sweep_ugv_low logs/ugv/stage4/tz_b33_spawn_ugv.txt logs/ugv/stage4/single_b_fleet.json $PY logs/ugv/stage4/sweep.py --rid B-ugv1 --subset logs/ugv/stage5/tiles/road_subset_tz_b33.json --n 6 --track-s 2000
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage5/coverage.py > /dev/null 2>&1
bash $RT c11_b_sweep_ugv logs/ugv/stage4/tz_b33_spawn_ugv.txt logs/ugv/stage4/single_b_fleet.json $PY logs/ugv/stage4/sweep.py --rid B-ugv1 --subset logs/ugv/stage5/tiles/road_subset_tz_b33.json --n 10 --track-s 2400
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage5/coverage.py > /dev/null 2>&1
bash $RT c11_b_sweep_fire logs/ugv/stage4/tz_b33_spawn_fire.txt logs/ugv/stage4/single_bfire_fleet.json $PY logs/ugv/stage4/sweep.py --rid B-fire1 --subset logs/ugv/stage5/tiles/road_subset_tz_b33.json --n 8 --track-s 2400
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage5/coverage.py > /dev/null 2>&1
echo CHAIN11_DONE
bash logs/ugv/stage4/chain12.sh > logs/ugv/stage4/chain12.out 2>&1
