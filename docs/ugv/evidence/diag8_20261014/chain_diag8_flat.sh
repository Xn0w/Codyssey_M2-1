#!/usr/bin/env bash
# 진단 8 평지 1회 — IMU 500 Hz 변형 (기준 logs/ugv/stage6/diag8/DIAG8_plan.md)
cd "$(dirname "$0")/../../.."
M=$(pwd); ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe
HK=../ADAIR_wt_hook; O=logs/ugv/stage6/diag8; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/$O; SL=logs/ugv/stage6/slope
[ "$(git -C $HK rev-parse --short HEAD)" = 03d5b5d ] || { echo "CHAIN_DIAG8F_HOLD HEAD 불일치"; exit 0; }
LT=/home/geumsoni/PX4-Autopilot/build/px4_sitl_default/etc/logging
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "mkdir -p $LT && cp $W/logger_topics.txt $LT/logger_topics.txt && sha1sum $LT/logger_topics.txt" > $O/logger_install.txt 2>&1
SUB=$ST/tiles_v2/road_subset_all_included.json
export SERVER_TREE=ADAIR_wt_hook
ON="UGV_STOP_CAP_FIRST=1 UGV_STOP_ITEMS_RAMP=1 UGV_PX4_PARK_AFTER_S=2.0 UGV_PX4_END_EXTEND=0 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
T=d8_flat500_s0547_a
env $ON GZ_REC_MODEL=adair_ugv_3 FLAT_Z=0 UGV_MODEL_VARIANT=susp_a_acc3_imu500 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB UGV_LAT_ACCEL=1.0 \
  bash logs/ugv/stage4/run_flat_v9.sh $T $O/s0547_flat_spawn.txt $SL/s0547_down_fleet.json \
  bash -c "cd $HK && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $T --rid B-ugv1 --model adair_ugv_3 --target-node RP:683400547:165.9 --track-s 200 --post-stop-s 50 --world kangwon_flat --abort-after 2 --abort-on-downhill 0.03" >> $O/run.out 2>&1
RC=$?
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "rm -f $LT/logger_topics.txt && rmdir $LT 2>/dev/null; ls $LT 2>&1 | head -1" >> $O/logger_install.txt 2>&1
echo "$T run rc=$RC rcfile=$(cat logs/ugv/stage4/rc_$T.json 2>/dev/null) verify=$(tail -1 logs/ugv/stage4/verify_$T.txt 2>/dev/null)" >> $O/run.out
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-3/log/*/*.ulg | head -1" > $O/ulog_$T.txt 2>&1
echo "CHAIN_DIAG8F_DONE $(date) rc=$RC"
