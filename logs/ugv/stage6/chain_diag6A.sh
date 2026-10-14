#!/usr/bin/env bash
# 진단 6 A 1회 (기준 logs/ugv/stage6/diag6/DIAG6_plan.md). 서버 03d5b5d. A 뒤 자동 진행 없음.
cd "$(dirname "$0")/../../.."
M=$(pwd); RT=logs/ugv/stage4/run_sc_v8.sh; ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe
HK=../ADAIR_wt_hook; O=logs/ugv/stage6/diag6; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/$O; SL=logs/ugv/stage6/slope
[ "$(git -C $HK rev-parse --short HEAD)" = 03d5b5d ] || { echo "CHAIN_DIAG6A_HOLD HEAD 불일치"; exit 0; }
AV=logs/ugv/stage6/av_diag
until grep -q AV_DIAG_DONE $AV/suite_parksamples.log 2>/dev/null; do sleep 20; done
tail -1 $AV/suite_parksamples/pytest.txt | grep -qE "^[0-9]+ passed in" || { echo "CHAIN_DIAG6A_HOLD $(date) 단위시험 통과 아님: $(tail -1 $AV/suite_parksamples/pytest.txt)"; exit 0; }
SUB=$ST/tiles_v2/road_subset_all_included.json
export SERVER_TREE=ADAIR_wt_hook
ON="UGV_STOP_CAP_FIRST=1 UGV_STOP_ITEMS_RAMP=1 UGV_PX4_PARK_AFTER_S=2.0 UGV_PX4_END_EXTEND=0 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
T=d6_on_s0547_downabort_A
env $ON UGV_MODEL_VARIANT=susp_a_acc3 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=wj495731_0574_0583 UGV_LAT_ACCEL=1.0 \
  bash $RT $T $SL/s0547_down_spawn.txt $SL/s0547_down_fleet.json \
  bash -c "cd $HK && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $T --rid B-ugv1 --model adair_ugv_3 --target-node RP:683400547:165.9 --track-s 200 --post-stop-s 50 --world wj495731_0574_0583 --abort-after 2 --abort-on-downhill 0.03" >> $O/run.out 2>&1
RC=$?
echo "$T run rc=$RC rcfile=$(cat logs/ugv/stage4/rc_$T.json 2>/dev/null)" >> $O/run.out
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-3/log/*/*.ulg | head -1" > $O/ulog_$T.txt 2>&1
U=$(tr -d '\r' < $O/ulog_$T.txt | tail -1)
for s in slope_ulog_dump ekf_drift_dump ekf_fusion_dump; do MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$s.py "$U" $W/${s}_$T.json >> $O/dump.out 2>&1; done
cp $O/slope_ulog_dump_$T.json $O/ulog_$T.json
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/ekf_signed.py "$U" -40,-20,0,4,6,8,10,15,20,25,30,35,40 > $O/signed_$T.txt 2>&1
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage6/slope_report.py --prefix d6_ --logs $HK/logs/ugv --out $M/$O/s4_slope_report.json > $O/s4_slope_report.out 2>&1
PYTHONIOENCODING=utf-8 $PY $O/slope5_judge.py > $O/judge.out 2>&1
echo "CHAIN_DIAG6A_DONE $(date) $(grep "^$T " $O/judge.out | awk '{print $2}')"
