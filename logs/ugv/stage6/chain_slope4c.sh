#!/usr/bin/env bash
# chain_slope4c (기록 창 --track-s 200, 첫 ON 재실행 a2) ← chain_slope4b (Codex 0155: 합본 전체 단위시험 게이트 + s0547 새 OFF + run_sc_v8). 원판: 2026-10-14 경사 정지 반복 (기준 logs/ugv/stage6/slope4/SLOPE4_criteria.md). 서버 ADAIR_wt_hook 899bb56, run_sc_v7.
cd "$(dirname "$0")/../../.."
M=$(pwd); RT=logs/ugv/stage4/run_sc_v8.sh; ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe
HK=../ADAIR_wt_hook; O=logs/ugv/stage6/slope4; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/$O; SL=logs/ugv/stage6/slope
[ "$(git -C $HK rev-parse --short HEAD)" = 899bb56 ] || { echo "CHAIN_SLOPE4_HOLD HEAD 불일치"; exit 0; }
AV=logs/ugv/stage6/av_diag
until grep -q AV_DIAG_DONE $AV/suite_899bb56.log 2>/dev/null; do sleep 20; done
tail -1 $AV/suite_899bb56/pytest.txt | grep -qE "^[0-9]+ passed in" || { echo "CHAIN_SLOPE4C_HOLD $(date) 합본 단위시험 통과 아님: $(tail -1 $AV/suite_899bb56/pytest.txt)"; exit 0; }
SUB=$ST/tiles_v2/road_subset_all_included.json
export SERVER_TREE=ADAIR_wt_hook
ON="UGV_STOP_CAP_FIRST=1 UGV_PX4_PARK_AFTER_S=2.0 UGV_PX4_END_EXTEND=0 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
OFF="UGV_STOP_CAP_FIRST=0 UGV_PX4_END_EXTEND=0 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
BAD=0
run() {   # tag variant case world rid inst target envset
  [ $BAD -ge 2 ] && { echo "$1 건너뜀 — 무효/중단 누적 $BAD" >> $O/run.out; return; }
  local T=$1
  env $8 UGV_MODEL_VARIANT=$2 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=$4 UGV_LAT_ACCEL=1.0 \
    bash $RT $T $SL/$3_spawn.txt $SL/$3_fleet.json \
    bash -c "cd $HK && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $T --rid $5 --model adair_ugv_$6 --target-node $7 --track-s 200 --post-stop-s 50 --world $4 --abort-after 2 --abort-on-downhill 0.03" >> $O/run.out 2>&1
  RC=$?
  echo "$T run rc=$RC rcfile=$(cat logs/ugv/stage4/rc_$T.json 2>/dev/null) verify=$(tail -1 logs/ugv/stage4/verify_$T.txt 2>/dev/null)" >> $O/run.out
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-$6/log/*/*.ulg | head -1" > $O/ulog_$T.txt 2>&1
  U=$(tr -d '\r' < $O/ulog_$T.txt | tail -1)
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/slope_ulog_dump.py "$U" $W/ulog_$T.json >> $O/ulog_dump.out 2>&1
  [ $RC = 0 ] || BAD=$((BAD+1))
}
judge() { PYTHONIOENCODING=utf-8 $PY logs/ugv/stage6/slope_report.py --prefix s4r_ --logs $HK/logs/ugv --out $M/$O/s4_slope_report.json > $O/s4_slope_report.out 2>&1; PYTHONIOENCODING=utf-8 $PY $O/slope4_judge.py > $O/judge.out 2>&1; }
C1="s0547_down wj495731_0574_0583 B-ugv1 3 RP:683400547:165.9"; C3="s3113_down wj494846_1237_1921 A-ugv1 1 RP:682503113:143.0"
# (OFF s0547 은 chain_slope4b 에서 완료)
run s4r_on_s0547_downabort_a2 susp_a_acc3 $C1 "$ON"
judge
FIRST=$(grep "^s4r_on_s0547_downabort_a2 " $O/judge.out | awk '{print $2}')
echo "SLOPE4C_FIRST $FIRST $(date)" >> $O/run.out
if [ "$FIRST" != PASS ]; then echo "CHAIN_SLOPE4C_DONE $(date) 첫 ON 회차 $FIRST — 나머지 실행 안 함"; cat $O/judge.out; exit 0; fi
run s4r_on_s0547_downabort_b susp_a_acc3 $C1 "$ON"
run s4r_on_s0547_downabort_c susp_a_acc3 $C1 "$ON"
run s4r_on_s3113_downabort_a susp_a_acc3 $C3 "$ON"
run s4r_on_s3113_downabort_b susp_a_acc3 $C3 "$ON"
run s4r_on_s3113_downabort_c susp_a_acc3 $C3 "$ON"
judge
echo "CHAIN_SLOPE4C_DONE $(date)"; cat $O/judge.out
