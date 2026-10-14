#!/usr/bin/env bash
# 2026-10-13 E3 — F2(d) RA_ACC_RAD_MAX 3 곡선 부작용 최소 비교 (Codex 1645). 기준 = docs/ugv/UGV_S4_경사_결과_20261013.md 'E3' 절 (결과 전 고정).
#   같은 서버 ADAIR_wt_integ_next 0a8a35a·후보 플래그 모두 0·곡선 도착 사례 s1096_down, 차량 변형만 susp_a / susp_a_acc3. 각 1회.
cd "$(dirname "$0")/../../.."
M=$(pwd); RT=logs/ugv/stage4/run_sc_v6.sh; ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe
NX=../ADAIR_wt_integ_next; O=logs/ugv/stage6/e3; mkdir -p $O
(cd $NX && git rev-parse HEAD > ../ADAIR/$O/head.txt)
SUB=$ST/tiles_v2/road_subset_all_included.json
export SERVER_TREE=ADAIR_wt_integ_next
E="UGV_STOP_CAP_FIRST=0 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
for pair in "e3base_s1096_down_a:susp_a" "e3acc_s1096_down_a:susp_a_acc3"; do
  TAG=${pair%%:*}; VAR=${pair##*:}
  env $E UGV_MODEL_VARIANT=$VAR UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=wj495663_1400_0021 UGV_LAT_ACCEL=1.0 \
    bash $RT $TAG logs/ugv/stage6/slope2/s1096_down_spawn.txt logs/ugv/stage6/slope2/s1096_down_fleet.json \
    bash -c "cd $NX && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $TAG --rid B-ugv1 --model adair_ugv_3 --target-node RP:683501096:10.0 --track-s 170 --post-stop-s 35 --world wj495663_1400_0021" >> $O/run.out 2>&1
  echo "$TAG run rc=$? verify=$(tail -1 logs/ugv/stage4/verify_$TAG.txt 2>/dev/null)" >> $O/run.out
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-3/log/*/*.ulg | head -1" > $O/ulog_$TAG.txt 2>&1
done
echo "CHAIN_E3_DONE $(date) $(grep 'run rc' $O/run.out | tr '\n' ' ')"
