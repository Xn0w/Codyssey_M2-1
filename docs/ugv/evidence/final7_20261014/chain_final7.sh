#!/usr/bin/env bash
# 최종 500 Hz 경사 검증 v7 — 입력 = 중단 요청 시점 Gazebo 속도 (기준 logs/ugv/stage6/final7/FINAL7_criteria.md (Codex 0705))
cd "$(dirname "$0")/../../.."
M=$(pwd); ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe
HK=../ADAIR_wt_hook; O=logs/ugv/stage6/final7; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/$O; SL=logs/ugv/stage6/slope
[ "$(git -C $HK rev-parse --short HEAD)" = 03d5b5d ] || { echo "CHAIN_FINAL7_HOLD 서버 HEAD 불일치"; exit 0; }
[ "$(git -C ../ADAIR_wt_vehicle rev-parse --short HEAD)" = 48f3e5f ] || { echo "CHAIN_FINAL7_HOLD 차량 HEAD 불일치"; exit 0; }
LT=/home/geumsoni/PX4-Autopilot/build/px4_sitl_default/etc/logging
SUB=$ST/tiles_v2/road_subset_all_included.json
export SERVER_TREE=ADAIR_wt_hook
ON="UGV_STOP_CAP_FIRST=1 UGV_STOP_ITEMS_RAMP=1 UGV_PX4_PARK_AFTER_S=2.0 UGV_PX4_END_EXTEND=0 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
declare -A CNT=([s3113]=0 [s0547]=0) TRY=([s3113]=0 [s0547]=0)
run() {   # case first?
  local C=$1 FIRST=$2; TRY[$C]=$((TRY[$C]+1)); local T=f7_on_${C}_downabort_${TRY[$C]}
  if [ $C = s0547 ]; then local CASE="s0547_down wj495731_0574_0583 B-ugv1 3 RP:683400547:165.9"; else local CASE="s3113_down wj494846_1237_1921 A-ugv1 1 RP:682503113:143.0"; fi
  set -- $CASE; local SC=$1 WD=$2 RID=$3 INST=$4 TGT=$5
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "mkdir -p $LT && cp $W/logger_topics.txt $LT/logger_topics.txt" >/dev/null 2>&1
  env $ON GZ_REC_MODEL=adair_ugv_$INST UGV_MODEL_VARIANT=susp_a_acc3_imu500 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=$WD UGV_LAT_ACCEL=1.0 \
    bash logs/ugv/stage4/run_sc_v9.sh $T $SL/${SC}_spawn.txt $SL/${SC}_fleet.json \
    bash -c "cd $HK && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $T --rid $RID --model adair_ugv_$INST --target-node $TGT --track-s 200 --post-stop-s 50 --world $WD --abort-after 2 --abort-on-downhill 0.03" >> $O/run.out 2>&1
  local RC=$?
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "rm -f $LT/logger_topics.txt && rmdir $LT 2>/dev/null; true" >/dev/null 2>&1
  echo "$T run rc=$RC rcfile=$(cat logs/ugv/stage4/rc_$T.json 2>/dev/null)" >> $O/run.out
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-$INST/log/*/*.ulg | head -1" > $O/ulog_$T.txt 2>&1
  local U=$(tr -d '\r' < $O/ulog_$T.txt | tail -1)
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/slope_ulog_dump.py "$U" $W/ulog_$T.json >> $O/dump.out 2>&1
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/imu_rate_check.py "$U" $W/imu_rate_$T.json >> $O/dump.out 2>&1
  [ "$FIRST" = first ] && MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/diag7_evidence_v2.py "$U" /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/logs/ugv/stage6/diag7/gzrec_$T $W/evidence_v2_$T.json --virtual250 >> $O/dump.out 2>&1
  PYTHONIOENCODING=utf-8 $PY logs/ugv/stage6/slope_report.py --prefix f7_ --logs $HK/logs/ugv --out $M/$O/s4_slope_report.json > $O/s4_slope_report.out 2>&1
  PYTHONIOENCODING=utf-8 $PY $O/final_judge_v7.py > $O/judge.out 2>&1
  local S=$(grep "^$T " $O/judge.out | awk '{print $2}')
  echo "FINAL7_RESULT $T $S $(date +%T)" >> $O/run.out
  [ $RC = 0 ] || { echo "CHAIN_FINAL7_DONE $(date) $T 래퍼 rc=$RC — 중단"; exit 0; }
  case "$S" in
    PASS) CNT[$C]=$((CNT[$C]+1));;
    *) echo "CHAIN_FINAL7_DONE $(date) $T $S — 비PASS(OUT_OF_RANGE 포함) 즉시 중단 (Codex 0705)"; exit 0;;
  esac
}
until [ ${CNT[s3113]} -ge 1 ]; do run s3113 first; done
until [ ${CNT[s0547]} -ge 1 ]; do run s0547 first; done
while [ ${CNT[s3113]} -lt 3 ] || [ ${CNT[s0547]} -lt 3 ]; do
  [ ${CNT[s3113]} -lt 3 ] && run s3113
  [ ${CNT[s0547]} -lt 3 ] && run s0547
done
echo "CHAIN_FINAL7_DONE $(date) s3113 ${CNT[s3113]}/${TRY[s3113]} s0547 ${CNT[s0547]}/${TRY[s0547]}"
