#!/usr/bin/env bash
# 2026-10-12 소방서 회전 공터(가정 시설) Gazebo 검증: 월드 tz_b33st2 (tiles_v2_st, T15~17×04~06), B-ugv1 → RP:683400483:14.7
# 계획: 거점 출발 방향 앞 노드 495728 회전 공터를 돌아 출입 도로를 되짚어 교량 683400483 (공터 없으면 도착 예정 351 s, 있으면 219 s). 복귀 포함
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v2.sh
until grep -q CHAIN31_DONE logs/ugv/stage4/chain31.out 2>/dev/null; do sleep 20; done
export TILES=tiles_v2_st EXTRA=stations
ENVX="UGV_ROAD_SUBSET=$M/logs/ugv/stage5/tiles_v2_st/road_subset_tz_b33st2.json UGV_EXTRA_ROADS=$M/logs/ugv/stage5/turn/stations_extra_roads.json ADAIR_TILES_OUT=$M/logs/ugv/stage5/tiles_v2_st"
WORLD=tz_b33st2 bash $RT c32_station_turn logs/ugv/stage4/tz_b33v2_spawn_ugv.txt logs/ugv/stage4/single_b_fleet.json bash -c "cd ../ADAIR_wt_turn && env $ENVX $PY -m ugv.tools.road_test --tag c32_station_turn --rid B-ugv1 --model adair_ugv_3 --target-node RP:683400483:14.7 --return-home --track-s 900 --world tz_b33st2"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN32_DONE $(date)"
