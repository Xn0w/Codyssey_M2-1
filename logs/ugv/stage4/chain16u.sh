#!/usr/bin/env bash
# 4번 접지 원인 분리 (UGV 만, 통합 사전 시험 이탈 뒤 우선): 평면 바닥 vs 평탄 높이장, 같은 경로·속도 30 km/h
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
TGT=RP:682501271:39.7
export UGV_MAX_SPEED_KMH=30
UGV_ROAD_SUBSET=$(pwd)/logs/ugv/stage5/tiles/road_subset_tz_a33.json bash logs/ugv/stage4/run_sc_wt.sh c16_plane_ugv logs/ugv/stage4/plane_spawn_ugv_a33start.txt logs/ugv/stage4/single_a_fleet.json $PY -m ugv.tools.road_test --tag c16_plane_ugv --rid A-ugv1 --model adair_ugv_1 --target-node $TGT --return-home --track-s 600 --world kangwon_flat
WORLD=tz_flathm bash logs/ugv/stage4/run_sc_tz.sh c16_flathm_ugv logs/ugv/stage4/flathm_spawn_ugv.txt logs/ugv/stage4/single_a_fleet.json $PY -m ugv.tools.road_test --tag c16_flathm_ugv --rid A-ugv1 --model adair_ugv_1 --target-node $TGT --return-home --track-s 600 --world tz_flathm
$PY logs/ugv/stage4/grip_compare.py --glob 'logs/ugv/c16_*ugv*.json' > logs/ugv/stage4/grip_compare_c16u.txt 2>&1
echo CHAIN16U_DONE
