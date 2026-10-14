#!/usr/bin/env bash
# 6단계 경사 성능 (정적 기준 밖 10 % 넘는 경사 — tz_a33 구역): 경사 위 정차 유지(60 s 밀림), 내리막 중단 제동. UGV·소방차
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
RT=logs/ugv/stage4/run_sc_tz.sh
export WORLD=tz_a33
TU=logs/ugv/stage4/tz_a33_spawn_ugv.txt; TF=logs/ugv/stage4/tz_a33_spawn_fire.txt
FU=logs/ugv/stage4/single_a_fleet.json; FF=logs/ugv/stage4/single_afire_fleet.json
UP=RP:682501580:160.0      # 일방 오르막 (213 → 230 m, 구간 최대 약 14 %)
DOWN=RP:682501581:200.0    # 일방 내리막 (223 → 213 m, 앞 60 m 약 10 %)
# 6단계 ③④ 재시험 (chain5 지형 시험은 타일 세로 축척 결함·스폰 불일치로 무효 → 9af4505 뒤 다시)
TGT=RP:682501271:39.7
bash $RT c8_tz_ugv_brake $TU $FU $PY -m ugv.tools.road_test --tag c8_tz_ugv_brake --target-node $TGT --return-home --abort-after 20 --abort-on-downhill 0.05 --track-s 900 --world tz_a33
bash $RT c8_tz_ugv_norm $TU $FU $PY -m ugv.tools.road_test --tag c8_tz_ugv_norm --target-node $TGT --return-home --track-s 900 --world tz_a33
bash $RT c8_tz_follow logs/ugv/stage4/tz_a33_spawn_pair.txt logs/ugv/stage4/pair_a_fleet.json $PY -m ugv.tools.fleet_test follow --track-s 1200
bash $RT c8_tz_ugv_hold $TU $FU $PY -m ugv.tools.road_test --tag c8_tz_ugv_hold --target-node $UP --dwell-s 60 --return-home --track-s 900 --world tz_a33
bash $RT c8_tz_fire_hold $TF $FF $PY -m ugv.tools.road_test --tag c8_tz_fire_hold --rid A-fire1 --model adair_firetruck_2 --target-node $UP --dwell-s 60 --return-home --track-s 900 --world tz_a33
bash $RT c8_tz_ugv_down $TU $FU $PY -m ugv.tools.road_test --tag c8_tz_ugv_down --target-node $DOWN --abort-after 5 --abort-on-downhill 0.06 --return-home --track-s 900 --world tz_a33
bash $RT c8_tz_fire_down $TF $FF $PY -m ugv.tools.road_test --tag c8_tz_fire_down --rid A-fire1 --model adair_firetruck_2 --target-node $DOWN --abort-after 5 --abort-on-downhill 0.06 --return-home --track-s 900 --world tz_a33
echo CHAIN8_DONE
