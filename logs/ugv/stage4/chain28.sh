#!/usr/bin/env bash
# 2026-10-11 경사 주행 시험 (사용자 요청): B 거점 구역 tz_b33, 코드 38aa911 그대로. 목표 RP:683400617:57.1
# 1차(c27) 목표가 교차로 12 m 앞이라 복귀 계획 불가(알려진 결함 2) → 경사 구간(683400481 s58 13.8 %) 지나 교차로에서 57 m 떨어진 곳으로.
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
RT=logs/ugv/stage4/run_sc_tz.sh
export WORLD=tz_b33
TGT=RP:683400617:57.1
bash $RT c28_slope_ugv logs/ugv/stage4/tz_b33_spawn_ugv.txt logs/ugv/stage4/single_b_fleet.json $PY -m ugv.tools.road_test --tag c28_slope_ugv --rid B-ugv1 --model adair_ugv_3 --target-node $TGT --dwell-s 60 --return-home --track-s 600 --world tz_b33
bash $RT c28_slope_fire logs/ugv/stage4/tz_b33_spawn_fire.txt logs/ugv/stage4/single_bfire_fleet.json $PY -m ugv.tools.road_test --tag c28_slope_fire --rid B-fire1 --model adair_firetruck_4 --target-node $TGT --dwell-s 60 --return-home --track-s 600 --world tz_b33
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN28_DONE $(date)"
