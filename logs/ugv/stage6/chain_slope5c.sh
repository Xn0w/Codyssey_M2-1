#!/usr/bin/env bash
# chain_slope5c (서버 b9fe46b — start_item 0 기록, 첫 회차 a2) ← chain_slope5b (단위시험 게이트 = suite_stopramp2 — 첫 시도 접근 위반) ← chain_slope5 (2026-10-14, 기준 logs/ugv/stage6/slope5/SLOPE5_criteria.md): 서버 ADAIR_wt_hook 341df20, 매 회차 판정·PASS 아니면 즉시 중단
cd "$(dirname "$0")/../../.."
M=$(pwd); RT=logs/ugv/stage4/run_sc_v8.sh; ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe
HK=../ADAIR_wt_hook; O=logs/ugv/stage6/slope5; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/$O; SL=logs/ugv/stage6/slope
[ "$(git -C $HK rev-parse --short HEAD)" = b9fe46b ] || { echo "CHAIN_SLOPE5_HOLD HEAD 불일치"; exit 0; }
AV=logs/ugv/stage6/av_diag
until grep -q AV_DIAG_DONE $AV/suite_stopramp2.log 2>/dev/null; do sleep 20; done
tail -1 $AV/suite_stopramp2/pytest.txt | grep -qE "^[0-9]+ passed in" || { echo "CHAIN_SLOPE5_HOLD $(date) 단위시험 통과 아님: $(tail -1 $AV/suite_stopramp2/pytest.txt)"; exit 0; }
SUB=$ST/tiles_v2/road_subset_all_included.json
export SERVER_TREE=ADAIR_wt_hook
ON="UGV_STOP_CAP_FIRST=1 UGV_STOP_ITEMS_RAMP=1 UGV_PX4_PARK_AFTER_S=2.0 UGV_PX4_END_EXTEND=0 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
run() {   # tag variant case world rid inst target envset
  local T=$1
  env $8 UGV_MODEL_VARIANT=$2 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=$4 UGV_LAT_ACCEL=1.0 \
    bash $RT $T $SL/$3_spawn.txt $SL/$3_fleet.json \
    bash -c "cd $HK && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $T --rid $5 --model adair_ugv_$6 --target-node $7 --track-s 200 --post-stop-s 50 --world $4 --abort-after 2 --abort-on-downhill 0.03" >> $O/run.out 2>&1
  RC=$?
  echo "$T run rc=$RC rcfile=$(cat logs/ugv/stage4/rc_$T.json 2>/dev/null) verify=$(tail -1 logs/ugv/stage4/verify_$T.txt 2>/dev/null)" >> $O/run.out
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-$6/log/*/*.ulg | head -1" > $O/ulog_$T.txt 2>&1
  U=$(tr -d '\r' < $O/ulog_$T.txt | tail -1)
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/slope_ulog_dump.py "$U" $W/ulog_$T.json >> $O/ulog_dump.out 2>&1
  PYTHONIOENCODING=utf-8 $PY logs/ugv/stage6/slope_report.py --prefix s5_ --logs $HK/logs/ugv --out $M/$O/s4_slope_report.json > $O/s4_slope_report.out 2>&1
  PYTHONIOENCODING=utf-8 $PY $O/slope5_judge.py > $O/judge.out 2>&1
  ST_=$(grep "^$T " $O/judge.out | awk '{print $2}')
  echo "SLOPE5_RESULT $T $ST_ $(date +%T)" >> $O/run.out
  [ "$ST_" = PASS ] || { echo "CHAIN_SLOPE5_DONE $(date) $T $ST_ — 중단 (비PASS)"; cat $O/judge.out; exit 0; }
}
C1="s0547_down wj495731_0574_0583 B-ugv1 3 RP:683400547:165.9"; C3="s3113_down wj494846_1237_1921 A-ugv1 1 RP:682503113:143.0"
run s5_on_s3113_downabort_a2 susp_a_acc3 $C3 "$ON"
run s5_on_s0547_downabort_a susp_a_acc3 $C1 "$ON"
run s5_on_s3113_downabort_b susp_a_acc3 $C3 "$ON"
run s5_on_s0547_downabort_b susp_a_acc3 $C1 "$ON"
run s5_on_s3113_downabort_c susp_a_acc3 $C3 "$ON"
run s5_on_s0547_downabort_c susp_a_acc3 $C1 "$ON"
echo "CHAIN_SLOPE5_DONE $(date) 6/6 PASS"; cat $O/judge.out
