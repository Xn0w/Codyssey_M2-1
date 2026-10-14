#!/usr/bin/env bash
# 실제 지형 제한적 환경 선별 (Codex 0814 2절, 기준 terrain_ab/ENVAB_criteria.md): 단계 A 정지 월드 확인 → PASS 면 단계 B 300 m 저속 (20 km/h) 정상 도착 1회. 비PASS 즉시 중단.
# 운영 S5 승격·원안 screen1 (2.38 km/60 km/h) 과 별개. 자동 장거리 후속 없음.
cd "$(dirname "$0")/../../.."
M=$(pwd); ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe
HK=../ADAIR_wt_hook; TA=logs/ugv/stage6/terrain_ab; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR
[ "$(git -C $HK rev-parse --short HEAD)" = 03d5b5d ] || { echo "CHAIN_ENVAB_HOLD 서버 HEAD 불일치"; exit 0; }
[ "$(git -C ../ADAIR_wt_vehicle rev-parse --short HEAD)" = 48f3e5f ] || { echo "CHAIN_ENVAB_HOLD 차량 HEAD 불일치"; exit 0; }
(cd $TA && sha1sum -c --quiet ENVAB_freeze.sha1) || { echo "CHAIN_ENVAB_HOLD 동결 해시 불일치"; exit 0; }
LT=/home/geumsoni/PX4-Autopilot/build/px4_sitl_default/etc/logging
SUB=$ST/tiles_v2/road_subset_ab_route_v1.json
export SERVER_TREE=ADAIR_wt_hook
OPS="UGV_STOP_CAP_FIRST=1 UGV_STOP_ITEMS_RAMP=1 UGV_PX4_END_EXTEND=1 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
probe_on() { MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "free -m | awk '/Mem:/ {print \$3\",\"\$7}'" > $1/mem_before_$2.txt 2>&1
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "(setsid nohup bash $W/$TA/rtf_mem_probe.sh ab_route_v1 $W/$1/probe_$2.csv 1200 > /dev/null 2>&1 < /dev/null & echo \$! > /tmp/probe_$2.pid)"; }
probe_off() { MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "kill \$(cat /tmp/probe_$2.pid) 2>/dev/null; pgrep -af 'gz sim|bin/px4' | grep -v pgrep | wc -l" > $1/residual_after_$2.txt 2>&1; }
ground() { MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$TA/screen_ground.py $W/logs/ugv/stage5/tiles_v2 $W/logs/ugv/stage6/diag7/gzrec_$2 $W/$1/ground_$2.json >> $1/dump.out 2>&1; }
echo "CHAIN_ENVAB_START $(date)"
# 단계 A — 미션 없이 90 s 정지
O=$TA/envA; T=ta1_idle_segB; probe_on $O $T
env $OPS UGV_MAX_SPEED_KMH=20 GZ_REC_MODEL=adair_ugv_1 UGV_MODEL_VARIANT=susp_a_acc3_imu500 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=ab_route_v1 UGV_LAT_ACCEL=1.0 \
  bash logs/ugv/stage4/run_sc_v10_ops.sh $T $TA/segB_spawn.txt $TA/segB_fleet.json bash $TA/envA/idle_poll.sh $O/poll_$T.jsonl >> $O/run.out 2>&1
RC=$?; probe_off $O $T; ground $O $T
echo "$T run rc=$RC rcfile=$(cat logs/ugv/stage4/rc_$T.json 2>/dev/null)" >> $O/run.out
PYTHONIOENCODING=utf-8 $PY $O/envA_check.py $T > $O/check.out 2>&1
S=$(grep "^$T " $O/check.out | awk '{print $2}'); echo "ENVAB_RESULT $T $S rc=$RC $(date +%T)" >> $O/run.out
[ "$RC" = 0 ] && [ "$S" = PASS ] || { echo "CHAIN_ENVAB_DONE $(date) 단계 A $S rc=$RC — 중단 (B 안 함)"; exit 0; }
# 단계 B — 300 m 저속 정상 도착
O=$TA/envB; T=tb1_segB_ugv_a; probe_on $O $T
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "mkdir -p $LT && cp $W/$O/logger_topics.txt $LT/logger_topics.txt" >/dev/null 2>&1
env $OPS UGV_MAX_SPEED_KMH=20 GZ_REC_MODEL=adair_ugv_1 UGV_MODEL_VARIANT=susp_a_acc3_imu500 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=ab_route_v1 UGV_LAT_ACCEL=1.0 \
  bash logs/ugv/stage4/run_sc_v10_ops.sh $T $TA/segB_spawn.txt $TA/segB_fleet.json \
  bash -c "cd $HK && env UGV_MAX_SPEED_KMH=20 UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $T --rid A-ugv1 --model adair_ugv_1 --target 38.06325574385999 128.17025179536637 --track-s 240 --post-stop-s 35 --world ab_route_v1" >> $O/run.out 2>&1
RC=$?; probe_off $O $T
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "rm -f $LT/logger_topics.txt && rmdir $LT 2>/dev/null; true" >/dev/null 2>&1
echo "$T run rc=$RC rcfile=$(cat logs/ugv/stage4/rc_$T.json 2>/dev/null)" >> $O/run.out
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-1/log/*/*.ulg | head -1" > $O/ulog_$T.txt 2>&1
U=$(tr -d '\r' < $O/ulog_$T.txt | tail -1)
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$O/e4_ulog_dump_v2.py "$U" $W/$O/ulog_v2_$T.json >> $O/dump.out 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$O/imu_rate_check.py "$U" $W/$O/imu_rate_$T.json >> $O/dump.out 2>&1
ground $O $T
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage6/slope_report.py --prefix tb1_ --logs $HK/logs/ugv --out $M/$O/tb1_slope_report.json > $O/tb1_slope_report.out 2>&1
E4_SR=tb1_slope_report.json PYTHONIOENCODING=utf-8 $PY $O/envB_judge.py > $O/judge.out 2>&1
PYTHONIOENCODING=utf-8 $PY $O/envB_extra.py $T > $O/extra.out 2>&1
S=$(grep "^$T " $O/judge.out | awk '{print $2}'); X=$(grep "^$T " $O/extra.out | awk '{print $2}')
echo "ENVAB_RESULT $T judge=$S extra=$X rc=$RC $(date +%T)" >> $O/run.out
echo "CHAIN_ENVAB_DONE $(date) A PASS, B judge=$S extra=$X rc=$RC — 오퍼스 보고 (자동 후속 없음)"
