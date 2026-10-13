#!/usr/bin/env bash
# S5 운영 조합 도착 회차만 (Codex 0806 3절 — 중단 회차 결과와 독립): 운영 s1096 곡선 도착 1. 기준 OPS5_criteria.md + 08:1x 절.
cd "$(dirname "$0")/../../.."
M=$(pwd); ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe
HK=../ADAIR_wt_hook; O=logs/ugv/stage6/ops5; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/$O
[ "$(git -C $HK rev-parse --short HEAD)" = 03d5b5d ] || { echo "CHAIN_OPS5B_HOLD 서버 HEAD 불일치"; exit 0; }
[ "$(git -C ../ADAIR_wt_vehicle rev-parse --short HEAD)" = 48f3e5f ] || { echo "CHAIN_OPS5B_HOLD 차량 HEAD 불일치"; exit 0; }
(cd $O && sha1sum -c --quiet OPS5_freeze.sha1) || { echo "CHAIN_OPS5B_HOLD 동결 해시 불일치"; exit 0; }
LT=/home/geumsoni/PX4-Autopilot/build/px4_sitl_default/etc/logging
SUB=$ST/tiles_v2/road_subset_all_included.json
export SERVER_TREE=ADAIR_wt_hook
# 운영 예정 조합 — PARK_AFTER 요청 없음, 서버 TEST_HOOKS=0 (run_sc_v10_ops)
OPS="UGV_STOP_CAP_FIRST=1 UGV_STOP_ITEMS_RAMP=1 UGV_PX4_END_EXTEND=1 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
pre() { MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "mkdir -p $LT && cp $W/logger_topics.txt $LT/logger_topics.txt" >/dev/null 2>&1; }
post() {  # tag inst dumper
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "rm -f $LT/logger_topics.txt && rmdir $LT 2>/dev/null; true" >/dev/null 2>&1
  echo "$1 run rc=$RC rcfile=$(cat logs/ugv/stage4/rc_$1.json 2>/dev/null)" >> $O/run.out
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-$2/log/*/*.ulg | head -1" > $O/ulog_$1.txt 2>&1
  local U=$(tr -d '\r' < $O/ulog_$1.txt | tail -1)
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$3 "$U" $W/$4 >> $O/dump.out 2>&1
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/imu_rate_check.py "$U" $W/imu_rate_$1.json >> $O/dump.out 2>&1
}
gate() { echo "OPS5B_RESULT $1 $2 $(date +%T)" >> $O/run.out; [ $RC = 0 ] || { echo "CHAIN_OPS5B_DONE $(date) $1 래퍼 rc=$RC — 중단"; exit 0; }; [ "$2" = PASS ] || { echo "CHAIN_OPS5B_DONE $(date) $1 $2 — 비PASS 중단"; exit 0; }; }
echo "CHAIN_OPS5B_START $(date)"
# 2) 운영 s1096 곡선 정상 도착
T=o5a_acc3_s1096_a; S1=logs/ugv/stage6/slope2/s1096_down; pre
env $OPS UGV_MODEL_VARIANT=susp_a_acc3_imu500 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=wj495663_1400_0021 UGV_LAT_ACCEL=1.0 \
  bash logs/ugv/stage4/run_sc_v10_ops.sh $T ${S1}_spawn.txt ${S1}_fleet.json \
  bash -c "cd $HK && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $T --rid B-ugv1 --model adair_ugv_3 --target-node RP:683501096:10.0 --track-s 170 --post-stop-s 35 --world wj495663_1400_0021" >> $O/run.out 2>&1
RC=$?; post $T 3 e4_ulog_dump_v2.py ulog_v2_$T.json
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage6/slope_report.py --prefix o5a_ --logs $HK/logs/ugv --out $M/$O/o5a_slope_report.json > $O/o5a_slope_report.out 2>&1
E4_SR=o5a_slope_report.json PYTHONIOENCODING=utf-8 $PY $O/e4_judge_ops.py > $O/judge_arrive.out 2>&1
gate $T "$(grep "^$T " $O/judge_arrive.out | awk '{print $2}')"
echo "CHAIN_OPS5B_DONE $(date) o5a 1/1 PASS"
