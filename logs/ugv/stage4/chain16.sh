#!/usr/bin/env bash
# 4번 지형 접지 원인 분리: 같은 차량·경로·속도(30 km/h, RP:682501271 왕복)로 평면 바닥(kangwon_flat) / 평탄 높이장(tz_flathm) /
# 실제 지형 높이장(tz_a33). 도로 부분집합은 셋 다 tz_a33 (235 도로, 같은 계획). 판정: logs/ugv/stage4/grip_compare.py
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
TGT=RP:682501271:39.7
export UGV_MAX_SPEED_KMH=30
for veh in fire ugv; do
  if [ $veh = fire ]; then RID=A-fire1; MODEL=adair_firetruck_2; FL=logs/ugv/stage4/single_afire_fleet.json; SP_FLAT=logs/ugv/stage4/flat_afire_spawn.txt; SP_FHM=logs/ugv/stage4/flathm_spawn_fire.txt; SP_T=logs/ugv/stage4/tz_a33_spawn_fire.txt
  else RID=A-ugv1; MODEL=adair_ugv_1; FL=logs/ugv/stage4/single_a_fleet.json; SP_FLAT=logs/ugv/stage4/plane_spawn_ugv_a33start.txt; SP_FHM=logs/ugv/stage4/flathm_spawn_ugv.txt; SP_T=logs/ugv/stage4/tz_a33_spawn_ugv.txt; fi
  UGV_ROAD_SUBSET=$(pwd)/logs/ugv/stage5/tiles/road_subset_tz_a33.json bash logs/ugv/stage4/run_sc_wt.sh c16_plane_$veh $SP_FLAT $FL $PY -m ugv.tools.road_test --tag c16_plane_$veh --rid $RID --model $MODEL --target-node $TGT --return-home --track-s 700 --world kangwon_flat
  WORLD=tz_flathm bash logs/ugv/stage4/run_sc_tz.sh c16_flathm_$veh $SP_FHM $FL $PY -m ugv.tools.road_test --tag c16_flathm_$veh --rid $RID --model $MODEL --target-node $TGT --return-home --track-s 700 --world tz_flathm
  WORLD=tz_a33 bash logs/ugv/stage4/run_sc_tz.sh c16_real_$veh $SP_T $FL $PY -m ugv.tools.road_test --tag c16_real_$veh --rid $RID --model $MODEL --target-node $TGT --return-home --track-s 700 --world tz_a33
done
$PY logs/ugv/stage4/grip_compare.py > logs/ugv/stage4/grip_compare_c16.txt 2>&1
echo CHAIN16_DONE
