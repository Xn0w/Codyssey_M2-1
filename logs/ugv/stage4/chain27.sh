#!/usr/bin/env bash
# 2026-10-11 경사 주행 시험 (사용자 요청): B 거점 구역 tz_b33, 코드 38aa911 그대로. 목표 RP:683400481:66.3
# 계획 경로 위 생성 충돌면: 오르막 50 m 창 11.6 %·10 m 창 13.5 %, 복귀 내리막. 도착 60 s 정차 유지 뒤 복귀.
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
RT=logs/ugv/stage4/run_sc_tz.sh
export WORLD=tz_b33
TGT=RP:683400481:66.3
bash $RT c27_slope_ugv logs/ugv/stage4/tz_b33_spawn_ugv.txt logs/ugv/stage4/single_b_fleet.json $PY -m ugv.tools.road_test --tag c27_slope_ugv --rid B-ugv1 --model adair_ugv_3 --target-node $TGT --dwell-s 60 --return-home --track-s 600 --world tz_b33
bash $RT c27_slope_fire logs/ugv/stage4/tz_b33_spawn_fire.txt logs/ugv/stage4/single_bfire_fleet.json $PY -m ugv.tools.road_test --tag c27_slope_fire --rid B-fire1 --model adair_firetruck_4 --target-node $TGT --dwell-s 60 --return-home --track-s 600 --world tz_b33
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN27_DONE $(date)"
