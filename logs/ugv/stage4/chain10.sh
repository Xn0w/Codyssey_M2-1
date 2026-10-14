#!/usr/bin/env bash
# 6단계 커버리지 순회 (정적 통과·아직 안 달린 링크): tz_a33 UGV 15곳, 회랑 UGV 10곳, tz_a33 소방차 8곳
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
RT=logs/ugv/stage4/run_sc_tz.sh
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage5/coverage.py > /dev/null 2>&1
WORLD=tz_a33 bash $RT c10_sweep_ugv logs/ugv/stage4/tz_a33_spawn_ugv.txt logs/ugv/stage4/single_a_fleet.json $PY logs/ugv/stage4/sweep.py --rid A-ugv1 --subset logs/ugv/stage5/tiles/road_subset_tz_a33.json --n 15 --track-s 3000
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage5/coverage.py > /dev/null 2>&1
WORLD=tc_A_ugv1_far bash $RT c10_sweep_tc logs/ugv/stage4/tc_A_ugv1_far_spawn.txt logs/ugv/stage4/single_a_fleet.json $PY logs/ugv/stage4/sweep.py --rid A-ugv1 --subset logs/ugv/stage5/tiles/road_subset_tc_A_ugv1_far.json --n 10 --track-s 2400
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage5/coverage.py > /dev/null 2>&1
WORLD=tz_a33 bash $RT c10_sweep_fire logs/ugv/stage4/tz_a33_spawn_fire.txt logs/ugv/stage4/single_afire_fleet.json $PY logs/ugv/stage4/sweep.py --rid A-fire1 --subset logs/ugv/stage5/tiles/road_subset_tz_a33.json --n 8 --track-s 2400
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage5/coverage.py > /dev/null 2>&1
echo CHAIN10_DONE
bash logs/ugv/stage4/chain8b.sh > logs/ugv/stage4/chain8b.out 2>&1
