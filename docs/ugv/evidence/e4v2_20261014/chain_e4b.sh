#!/usr/bin/env bash
# 2026-10-14 E4 v2 묶음 (기준 logs/ugv/stage6/e4/E4_criteria_v2.md). 서버 ADAIR_wt_hook 899bb56. E4-1 곡선 1회 → v2 판정 PASS 일 때만 나머지 3회.
cd "$(dirname "$0")/../../.."
M=$(pwd); RT=logs/ugv/stage4/run_sc_v7.sh; ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe
HK=../ADAIR_wt_hook; O=logs/ugv/stage6/e4; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/$O
[ "$(git -C $HK rev-parse --short HEAD)" = 899bb56 ] || { echo "CHAIN_E4B_HOLD 서버 트리 HEAD 불일치 $(git -C $HK rev-parse --short HEAD)"; exit 0; }
SUB=$ST/tiles_v2/road_subset_all_included.json
export SERVER_TREE=ADAIR_wt_hook
E="UGV_PX4_END_EXTEND=1 UGV_PX4_PARK_AFTER_S=2.0 UGV_STOP_CAP_FIRST=0 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
BAD=0   # 사용자 지시: 접근 위반·래퍼 무효가 묶음 누적 2회면 중단
run() {   # tag variant case world rid inst target
  [ $BAD -ge 2 ] && { echo "$1 건너뜀 — 무효/중단 누적 $BAD" >> $O/run_b.out; return; }
  local T=$1
  env $E UGV_MODEL_VARIANT=$2 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=$4 UGV_LAT_ACCEL=1.0 \
    bash $RT $T $3_spawn.txt $3_fleet.json \
    bash -c "cd $HK && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $T --rid $5 --model adair_ugv_$6 --target-node $7 --track-s 170 --post-stop-s 35 --world $4" >> $O/run_b.out 2>&1
  RC=$?
  echo "$T run rc=$RC rcfile=$(cat logs/ugv/stage4/rc_$T.json 2>/dev/null) verify=$(tail -1 logs/ugv/stage4/verify_$T.txt 2>/dev/null)" >> $O/run_b.out
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-$6/log/*/*.ulg | head -1" > $O/ulog_$T.txt 2>&1
  U=$(tr -d '\r' < $O/ulog_$T.txt | tail -1)
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/e4_ulog_dump_v2.py "$U" $W/ulog_v2_$T.json >> $O/ulog_dump_b.out 2>&1
  [ $RC = 0 ] || BAD=$((BAD+1))
}
judge() { PYTHONIOENCODING=utf-8 $PY logs/ugv/stage6/slope_report.py --prefix e4b_ --logs $HK/logs/ugv --out $M/$O/e4b_slope_report.json > $O/e4b_slope_report.out 2>&1; E4_SR=e4b_slope_report.json E4_PREFIX=e4b_ PYTHONIOENCODING=utf-8 $PY $O/e4_judge_v2.py > $O/e4b_judge_v2.out 2>&1; }
S1=logs/ugv/stage6/slope2/s1096_down; S3=logs/ugv/stage6/slope/s3113_down
run e4b_acc3_s1096_a susp_a_acc3 $S1 wj495663_1400_0021 B-ugv1 3 RP:683501096:10.0
judge
FIRST=$(grep "^e4b_acc3_s1096_a " $O/e4b_judge_v2.out | awk '{print $2}')
echo "E4B_FIRST $FIRST $(date)" >> $O/run_b.out
if [ "$FIRST" != PASS ]; then echo "CHAIN_E4B_DONE $(date) 첫 회차 $FIRST — 나머지 실행 안 함 (기준 v2)"; cat $O/e4b_judge_v2.out; exit 0; fi
run e4b_acc3_s1096_b susp_a_acc3 $S1 wj495663_1400_0021 B-ugv1 3 RP:683501096:10.0
run e4b_raoff_s1096_a susp_a $S1 wj495663_1400_0021 B-ugv1 3 RP:683501096:10.0
run e4b_acc3_s3113_a susp_a_acc3 $S3 wj494846_1237_1921 A-ugv1 1 RP:682503113:143.0
judge
echo "CHAIN_E4B_DONE $(date)"; cat $O/e4b_judge_v2.out
