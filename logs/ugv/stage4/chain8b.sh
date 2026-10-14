#!/usr/bin/env bash
# 6단계 경사 재시험: 구역 안에서 실제로 갈 수 있는 가장 가파른 도로 (약 11 %) — 정차 유지 60 s, 복귀 내리막 중단 제동. UGV·소방차
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
RT=logs/ugv/stage4/run_sc_tz.sh
export WORLD=tz_a33
TU=logs/ugv/stage4/tz_a33_spawn_ugv.txt; TF=logs/ugv/stage4/tz_a33_spawn_fire.txt
FU=logs/ugv/stage4/single_a_fleet.json; FF=logs/ugv/stage4/single_afire_fleet.json
H=RP:682500163:41.1     # 종단 최대 약 11 % (생성 충돌면)
D=RP:682501750:44.2     # 종단 최대 약 11 %, 복귀 때 내리막
bash $RT c8b_ugv_hold $TU $FU $PY -m ugv.tools.road_test --tag c8b_ugv_hold --target-node $H --dwell-s 60 --return-home --track-s 900 --world tz_a33
bash $RT c8b_fire_hold $TF $FF $PY -m ugv.tools.road_test --tag c8b_fire_hold --rid A-fire1 --model adair_firetruck_2 --target-node $H --dwell-s 60 --return-home --track-s 900 --world tz_a33
bash $RT c8b_ugv_down $TU $FU $PY -m ugv.tools.road_test --tag c8b_ugv_down --target-node $D --return-home --abort-after 20 --abort-on-downhill 0.06 --track-s 900 --world tz_a33
bash $RT c8b_fire_down $TF $FF $PY -m ugv.tools.road_test --tag c8b_fire_down --rid A-fire1 --model adair_firetruck_2 --target-node $D --return-home --abort-after 20 --abort-on-downhill 0.06 --track-s 900 --world tz_a33
bash $RT c8b_follow logs/ugv/stage4/tz_a33_spawn_pair.txt logs/ugv/stage4/pair_a_fleet.json $PY -m ugv.tools.fleet_test follow --track-s 1200
echo CHAIN8B_DONE
