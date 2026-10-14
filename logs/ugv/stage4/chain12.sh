#!/usr/bin/env bash
# 높이장 접촉 모델 확인: 높이 0 인 평평한 높이장 타일 (tz_flathm) 에서 평탄 월드(평면 바닥)와 같은 소방차 저속 왕복 (d5: 이탈 0)
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
WORLD=tz_flathm UGV_MAX_SPEED_KMH=30 bash logs/ugv/stage4/run_sc_tz.sh c12_flathm_fire logs/ugv/stage4/flathm_spawn_fire.txt logs/ugv/stage4/single_afire_fleet.json $PY -m ugv.tools.road_test --tag c12_flathm_fire --rid A-fire1 --model adair_firetruck_2 --target-node RP:682501271:39.7 --return-home --track-s 700 --world tz_flathm
echo CHAIN12_DONE
bash logs/ugv/stage4/chain13.sh > logs/ugv/stage4/chain13.out 2>&1
