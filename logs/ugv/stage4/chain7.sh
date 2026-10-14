#!/usr/bin/env bash
# 6단계 ⑤ 지형 구역 4대, ⑥·⑦ 타일 경계 여러 개를 지나는 실제 소방서(A) 출발·복귀 회랑 (교량 없이 닿는 가장 먼 곳 3.6 km)
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
RT=logs/ugv/stage4/run_sc_tz.sh
WORLD=tz_a33 bash $RT c7_tz_four logs/ugv/stage4/tz_a33_four_spawn.txt logs/ugv/stage4/tz_a33_four_fleet.json $PY logs/ugv/stage4/tz_four.py --track-s 1500
WORLD=tc_A_ugv1_far bash $RT c7_tc_ugv_far logs/ugv/stage4/tc_A_ugv1_far_spawn.txt logs/ugv/stage4/single_a_fleet.json $PY -m ugv.tools.road_test --tag c7_tc_ugv_far --target-node RP:682600552:17.3 --return-home --track-s 1200 --world tc_A_ugv1_far
WORLD=tc_A_ugv1_far bash $RT c7_tc_ugv_far2 logs/ugv/stage4/tc_A_ugv1_far_spawn.txt logs/ugv/stage4/single_a_fleet.json $PY -m ugv.tools.road_test --tag c7_tc_ugv_far2 --target-node RP:682600552:17.3 --return-home --track-s 1200 --world tc_A_ugv1_far
WORLD=tz_a33 bash $RT c7_tz_fire_up logs/ugv/stage4/tz_a33_spawn_fire.txt logs/ugv/stage4/single_afire_fleet.json $PY -m ugv.tools.road_test --tag c7_tz_fire_up --rid A-fire1 --model adair_firetruck_2 --target-node RP:682501123:62.0 --return-home --track-s 1000 --world tz_a33
# 4단계 총괄 폐루프 재시험 (복귀 결함 cc41d8c·총괄 연락 유지 9c04b30 뒤)
RW=logs/ugv/stage4/run_sc_wt.sh
bash $RW c7_orch_loop ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY logs/ugv/stage4/orch_loop.py --scenario loop --tag gz_loop2 --track-s 1800
echo CHAIN7_DONE
