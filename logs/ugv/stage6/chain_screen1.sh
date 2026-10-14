#!/usr/bin/env bash
# 실제 지형 ab_route_v1 짧은 선별 1회 (기준 logs/ugv/stage6/terrain_ab/screen1/SCREEN1_criteria.md, Codex 0755 3절) — S5 운영 조합 확인 2/2 PASS 뒤에만.
cd "$(dirname "$0")/../../.."
M=$(pwd); ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe
HK=../ADAIR_wt_hook; O=logs/ugv/stage6/terrain_ab/screen1; TA=logs/ugv/stage6/terrain_ab; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR
until grep -q "CHAIN_OPS5_DONE" logs/ugv/stage6/chain_ops5.out 2>/dev/null; do sleep 30; done
grep -q "CHAIN_OPS5_DONE.*2/2 PASS" logs/ugv/stage6/chain_ops5.out || { echo "CHAIN_SCREEN1_HOLD 운영 조합 확인 미통과: $(grep CHAIN_OPS5_DONE logs/ugv/stage6/chain_ops5.out)"; exit 0; }
[ "$(git -C $HK rev-parse --short HEAD)" = 03d5b5d ] || { echo "CHAIN_SCREEN1_HOLD 서버 HEAD 불일치"; exit 0; }
[ "$(git -C ../ADAIR_wt_vehicle rev-parse --short HEAD)" = 48f3e5f ] || { echo "CHAIN_SCREEN1_HOLD 차량 HEAD 불일치"; exit 0; }
(cd $O && sha1sum -c --quiet SCREEN1_freeze.sha1) || { echo "CHAIN_SCREEN1_HOLD 동결 해시 불일치"; exit 0; }
echo "CHAIN_SCREEN1_START $(date)"
LT=/home/geumsoni/PX4-Autopilot/build/px4_sitl_default/etc/logging
SUB=$ST/tiles_v2/road_subset_ab_route_v1.json
export SERVER_TREE=ADAIR_wt_hook
OPS="UGV_STOP_CAP_FIRST=1 UGV_STOP_ITEMS_RAMP=1 UGV_PX4_END_EXTEND=1 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
T=ts1_screenA_ugv_a
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "free -m | awk '/Mem:/ {print \$3\",\"\$7}'" > $O/mem_before_$T.txt 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "(setsid nohup bash $W/$TA/rtf_mem_probe.sh ab_route_v1 $W/$O/probe_$T.csv 1500 > /dev/null 2>&1 < /dev/null & echo \$! > /tmp/probe_$T.pid)"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "mkdir -p $LT && cp $W/$O/logger_topics.txt $LT/logger_topics.txt" >/dev/null 2>&1
env $OPS GZ_REC_MODEL=adair_ugv_1 UGV_MODEL_VARIANT=susp_a_acc3_imu500 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=ab_route_v1 UGV_LAT_ACCEL=1.0 \
  bash logs/ugv/stage4/run_sc_v10_ops.sh $T $TA/screen_A_ugv_spawn.txt $TA/screen_A_ugv_fleet.json \
  bash -c "cd $HK && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $T --rid A-ugv1 --model adair_ugv_1 --target 38.07317541264574 128.18216961281541 --track-s 600 --post-stop-s 35 --world ab_route_v1" >> $O/run.out 2>&1
RC=$?
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "kill \$(cat /tmp/probe_$T.pid) 2>/dev/null; pgrep -af 'gz sim|bin/px4' | grep -v pgrep | wc -l" > $O/residual_after_$T.txt 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "rm -f $LT/logger_topics.txt && rmdir $LT 2>/dev/null; true" >/dev/null 2>&1
echo "$T run rc=$RC rcfile=$(cat logs/ugv/stage4/rc_$T.json 2>/dev/null)" >> $O/run.out
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-1/log/*/*.ulg | head -1" > $O/ulog_$T.txt 2>&1
U=$(tr -d '\r' < $O/ulog_$T.txt | tail -1)
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$O/e4_ulog_dump_v2.py "$U" $W/$O/ulog_v2_$T.json >> $O/dump.out 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$O/imu_rate_check.py "$U" $W/$O/imu_rate_$T.json >> $O/dump.out 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$TA/screen_ground.py $W/logs/ugv/stage5/tiles_v2 $W/logs/ugv/stage6/diag7/gzrec_$T $W/$O/ground_$T.json >> $O/dump.out 2>&1
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage6/slope_report.py --prefix ts1_ --logs $HK/logs/ugv --out $M/$O/ts1_slope_report.json > $O/ts1_slope_report.out 2>&1
E4_SR=ts1_slope_report.json PYTHONIOENCODING=utf-8 $PY $O/screen_judge.py > $O/judge.out 2>&1
S=$(grep "^$T " $O/judge.out | awk '{print $2}')
echo "SCREEN1_RESULT $T $S rc=$RC $(date +%T)" >> $O/run.out
echo "CHAIN_SCREEN1_DONE $(date) $T $S rc=$RC (성능·접지 특성은 probe/ground 파일 — 오퍼스 판정 보고)"
