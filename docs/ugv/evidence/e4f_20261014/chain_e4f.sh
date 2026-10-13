#!/usr/bin/env bash
# 최종 500 Hz 후보 정상 도착 회귀 E4f (기준 logs/ugv/stage6/e4f/E4F_criteria.md, Codex 0650/0723) — 경사 v7.1 6 유효 완료 뒤에만 직렬 시작.
cd "$(dirname "$0")/../../.."
M=$(pwd); ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe
HK=../ADAIR_wt_hook; O=logs/ugv/stage6/e4f; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/$O
# 게이트: 경사 체인이 각 사례 3/3 으로 끝났을 때만
until grep -q "CHAIN_FINAL7R_DONE" logs/ugv/stage6/chain_final7r.out 2>/dev/null; do sleep 30; done
L=$(grep "CHAIN_FINAL7R_DONE" logs/ugv/stage6/chain_final7r.out | tail -1)
echo "$L" | grep -qE "s3113 3/[0-9]+ s0547 3/[0-9]+" || { echo "CHAIN_E4F_HOLD 경사 6 유효 미완료: $L"; exit 0; }
[ "$(git -C $HK rev-parse --short HEAD)" = 03d5b5d ] || { echo "CHAIN_E4F_HOLD 서버 HEAD 불일치"; exit 0; }
[ "$(git -C ../ADAIR_wt_vehicle rev-parse --short HEAD)" = 48f3e5f ] || { echo "CHAIN_E4F_HOLD 차량 HEAD 불일치"; exit 0; }
echo "CHAIN_E4F_START $(date)"
LT=/home/geumsoni/PX4-Autopilot/build/px4_sitl_default/etc/logging
SUB=$ST/tiles_v2/road_subset_all_included.json
export SERVER_TREE=ADAIR_wt_hook
E="UGV_STOP_CAP_FIRST=1 UGV_STOP_ITEMS_RAMP=1 UGV_PX4_END_EXTEND=1 UGV_PX4_PARK_AFTER_S=2.0 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
run() {   # tag case world rid inst target
  local T=$1
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "mkdir -p $LT && cp $W/logger_topics.txt $LT/logger_topics.txt" >/dev/null 2>&1
  env $E UGV_MODEL_VARIANT=susp_a_acc3_imu500 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=$3 UGV_LAT_ACCEL=1.0 \
    bash logs/ugv/stage4/run_sc_v9.sh $T $2_spawn.txt $2_fleet.json \
    bash -c "cd $HK && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $T --rid $4 --model adair_ugv_$5 --target-node $6 --track-s 170 --post-stop-s 35 --world $3" >> $O/run.out 2>&1
  local RC=$?
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "rm -f $LT/logger_topics.txt && rmdir $LT 2>/dev/null; true" >/dev/null 2>&1
  echo "$T run rc=$RC rcfile=$(cat logs/ugv/stage4/rc_$T.json 2>/dev/null)" >> $O/run.out
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-$5/log/*/*.ulg | head -1" > $O/ulog_$T.txt 2>&1
  local U=$(tr -d '\r' < $O/ulog_$T.txt | tail -1)
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/e4_ulog_dump_v2.py "$U" $W/ulog_v2_$T.json >> $O/dump.out 2>&1
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/imu_rate_check.py "$U" $W/imu_rate_$T.json >> $O/dump.out 2>&1
  PYTHONIOENCODING=utf-8 $PY logs/ugv/stage6/slope_report.py --prefix e4f_ --logs $HK/logs/ugv --out $M/$O/e4f_slope_report.json > $O/e4f_slope_report.out 2>&1
  E4_SR=e4f_slope_report.json PYTHONIOENCODING=utf-8 $PY $O/e4_judge_v3.py > $O/judge.out 2>&1
  local S=$(grep "^$T " $O/judge.out | awk '{print $2}')
  echo "E4F_RESULT $T $S $(date +%T)" >> $O/run.out
  [ $RC = 0 ] || { echo "CHAIN_E4F_DONE $(date) $T 래퍼 rc=$RC — 중단"; exit 0; }
  [ "$S" = PASS ] || { echo "CHAIN_E4F_DONE $(date) $T $S — 비PASS 즉시 중단"; exit 0; }
}
S1=logs/ugv/stage6/slope2/s1096_down; S3=logs/ugv/stage6/slope/s3113_down
run e4f_acc3_s1096_a $S1 wj495663_1400_0021 B-ugv1 3 RP:683501096:10.0
run e4f_acc3_s1096_b $S1 wj495663_1400_0021 B-ugv1 3 RP:683501096:10.0
run e4f_acc3_s3113_a $S3 wj494846_1237_1921 A-ugv1 1 RP:682503113:143.0
echo "CHAIN_E4F_DONE $(date) 3/3 PASS"
