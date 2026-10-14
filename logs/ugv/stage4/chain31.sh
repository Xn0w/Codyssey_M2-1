#!/usr/bin/env bash
# 2026-10-12 트윈 지도 정제 v2 Gazebo 검증 (3단계 판정의 ③): 코드 ../ADAIR_wt_turn (wip/turnaround), 타일 logs/ugv/stage5/tiles_v2
# G1a 발표 구역 회귀 tz_a33v2: A-ugv1 → RP:682501105:65.5 (통합 시험 UGV 목표) 복귀
# G1b tz_a33v2 교량 2개 경로: A-ugv1 → RP:682501336:293.4 (교량 682501349·682501165) 복귀
# G2  tz_b33v2 교량 176 m(성토 5.5 m): B-fire1 → RP:683400557:69.5 (교량 683400547) 복귀
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh
export TILES=tiles_v2
envx() { echo "UGV_ROAD_SUBSET=$M/logs/ugv/stage5/tiles_v2/road_subset_$1.json ADAIR_TILES_OUT=$M/logs/ugv/stage5/tiles_v2"; }
WORLD=tz_a33v2 bash $RT c31_a33_integ logs/ugv/stage4/tz_a33v2_spawn_ugv.txt logs/ugv/stage4/single_a_fleet.json bash -c "cd ../ADAIR_wt_turn && env $(envx tz_a33v2) $PY -m ugv.tools.road_test --tag c31_a33_integ --rid A-ugv1 --model adair_ugv_1 --target-node RP:682501105:65.5 --return-home --track-s 600 --world tz_a33v2"
WORLD=tz_a33v2 bash $RT c31_a33_bridge logs/ugv/stage4/tz_a33v2_spawn_ugv.txt logs/ugv/stage4/single_a_fleet.json bash -c "cd ../ADAIR_wt_turn && env $(envx tz_a33v2) $PY -m ugv.tools.road_test --tag c31_a33_bridge --rid A-ugv1 --model adair_ugv_1 --target-node RP:682501336:293.4 --return-home --track-s 900 --world tz_a33v2"
WORLD=tz_b33v2 bash $RT c31_b33_bridge_fire logs/ugv/stage4/tz_b33v2_spawn_fire.txt logs/ugv/stage4/single_bfire_fleet.json bash -c "cd ../ADAIR_wt_turn && env $(envx tz_b33v2) $PY -m ugv.tools.road_test --tag c31_b33_bridge_fire --rid B-fire1 --model adair_firetruck_4 --target-node RP:683400557:69.5 --return-home --track-s 900 --world tz_b33v2"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN31_DONE $(date)"
