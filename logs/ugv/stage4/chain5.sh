#!/usr/bin/env bash
# 3단계 보완(평탄 A: 같은 방향 따라가기 2회, 정지 차 앞 접근 3회차) + 6단계 ①~④ (트윈 지형 타일 구역 tz_a33, 기존 B 제한 구역 자리)
# 서버 = 작업트리 코드 (곡선 보정·막힘 거절·도착 정지 확인·성능)
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
RW=logs/ugv/stage4/run_sc_wt.sh
for n in 1 2; do
  bash $RW c5_follow_$n ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY -m ugv.tools.fleet_test follow --track-s 900
done
bash $RW c5_static_ahead_3 logs/ugv/pair_static_ahead_spawn.txt logs/ugv/pair_static_ahead_fleet.json $PY -m ugv.tools.pair_test run static_ahead --track-s 300 --after-s 20
export WORLD=tz_a33
RT=logs/ugv/stage4/run_sc_tz.sh
TU=logs/ugv/stage4/tz_a33_spawn_ugv.txt; TF=logs/ugv/stage4/tz_a33_spawn_fire.txt; TP=logs/ugv/stage4/tz_a33_spawn_pair.txt
FU=logs/ugv/stage4/single_a_fleet.json; FF=logs/ugv/stage4/single_afire_fleet.json; FP=logs/ugv/stage4/pair_a_fleet.json
TGT=RP:682501271:39.7     # A 출발 오르막 8 % (40 m 창), 복귀 때 같은 길 내리막
# ① UGV 단독 저속 30 km/h, ② 소방차 단독 저속
UGV_MAX_SPEED_KMH=30 bash $RT c5_tz_ugv_low $TU $FU $PY -m ugv.tools.road_test --tag c5_tz_ugv_low --target-node $TGT --return-home --track-s 900 --world tz_a33
UGV_MAX_SPEED_KMH=30 bash $RT c5_tz_fire_low $TF $FF $PY -m ugv.tools.road_test --tag c5_tz_fire_low --rid A-fire1 --model adair_firetruck_2 --target-node $TGT --return-home --track-s 900 --world tz_a33
# ③ 정상 속도 + 복귀 내리막(5 % 이상)에서 중단 — 경사 제동
bash $RT c5_tz_ugv_brake $TU $FU $PY -m ugv.tools.road_test --tag c5_tz_ugv_brake --target-node $TGT --return-home --abort-after 20 --abort-on-downhill 0.05 --track-s 900 --world tz_a33
bash $RT c5_tz_fire_brake $TF $FF $PY -m ugv.tools.road_test --tag c5_tz_fire_brake --rid A-fire1 --model adair_firetruck_2 --target-node $TGT --return-home --abort-after 20 --abort-on-downhill 0.05 --track-s 900 --world tz_a33
# ④ UGV + 소방차 (같은 길 앞뒤, 복귀)
bash $RT c5_tz_follow $TP $FP $PY -m ugv.tools.fleet_test follow --track-s 1200
echo CHAIN5_DONE
