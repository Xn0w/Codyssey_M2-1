#!/usr/bin/env bash
# 4번: 바퀴 충돌체 원기둥 → 구 (시험 모델 사본 logs/ugv/stage4/model_variants/sphere_wheels, 원본 미수정) — 평탄 높이장·실제 지형, 같은 경로·속도
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
TGT=RP:682501271:39.7
export UGV_MAX_SPEED_KMH=30
export GZ_MODEL_OVERRIDE=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/logs/ugv/stage4/model_variants/sphere_wheels
WORLD=tz_flathm bash logs/ugv/stage4/run_sc_tz.sh c16_flathm_ugv_sph logs/ugv/stage4/flathm_spawn_ugv.txt logs/ugv/stage4/single_a_fleet.json $PY -m ugv.tools.road_test --tag c16_flathm_ugv_sph --rid A-ugv1 --model adair_ugv_1 --target-node $TGT --return-home --track-s 600 --world tz_flathm
WORLD=tz_a33 bash logs/ugv/stage4/run_sc_tz.sh c16_real_ugv_sph logs/ugv/stage4/tz_a33_spawn_ugv.txt logs/ugv/stage4/single_a_fleet.json $PY -m ugv.tools.road_test --tag c16_real_ugv_sph --rid A-ugv1 --model adair_ugv_1 --target-node $TGT --return-home --track-s 600 --world tz_a33
$PY logs/ugv/stage4/grip_compare.py --glob 'logs/ugv/c16_*ugv*.json' > logs/ugv/stage4/grip_compare_c16s.txt 2>&1
echo CHAIN16S_DONE
