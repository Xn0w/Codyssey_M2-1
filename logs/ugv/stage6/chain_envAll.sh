#!/usr/bin/env bash
# 전 타일 보정 tiles_v2c1 월드 회귀 (2026-10-14 사용자 최우선: 실제 지형 이음매 0.976 m 틈 전 타일 수정) — 원 B 조건 (300 m·20 km/h·운영 조합) 그대로, 월드만 tiles_v2c1 (160 타일 전부 보정). 기준 terrain_ab/envAll/ENVALL_criteria.md. 원 설명: A 재실행 (Codex 1000: 고율 기록기 생명주기·준비·감시 게이트 수정, 새 ID tb2_segB_c1_b). 원 설명 — A 단계 (Codex 0940 2절 A): 원 B 조건 (tb1_segB_ugv_a 와 같은 스폰·목표·300 m·20 km/h·운영 조합) + 후보 c1 (T04_16·T05_16 충돌 size 보정) 1 회.
# 기준 terrain_ab/envB_c1/ENVB_C1_criteria.md. 비PASS 면 멈춤·보고. 자동 후속 없음.
cd "$(dirname "$0")/../../.."
M=$(pwd); ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe
HK=../ADAIR_wt_hook; TA=logs/ugv/stage6/terrain_ab; O=$TA/envAll; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR
[ "$(git -C $HK rev-parse --short HEAD)" = 03d5b5d ] || { echo "CHAIN_ENVALL_HOLD 서버 HEAD 불일치"; exit 0; }
[ "$(git -C ../ADAIR_wt_vehicle rev-parse --short HEAD)" = 48f3e5f ] || { echo "CHAIN_ENVALL_HOLD 차량 HEAD 불일치"; exit 0; }
(cd $O && sha1sum -c --quiet ENVALL_freeze.sha1) || { echo "CHAIN_ENVALL_HOLD 동결 해시 불일치"; exit 0; }
LT=/home/geumsoni/PX4-Autopilot/build/px4_sitl_default/etc/logging
SUB=$ST/tiles_v2c1/road_subset_ab_route_v1.json
export SERVER_TREE=ADAIR_wt_hook
OPS="UGV_STOP_CAP_FIRST=1 UGV_STOP_ITEMS_RAMP=1 UGV_PX4_END_EXTEND=1 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
T=tb3_segB_all_a
echo "CHAIN_ENVALL_START $(date)"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "free -m | awk '/Mem:/ {print \$3\",\"\$7}'" > $O/mem_before_$T.txt 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "(setsid nohup bash $W/$TA/rtf_mem_probe.sh ab_route_v1 $W/$O/probe_$T.csv 1200 > /dev/null 2>&1 < /dev/null & echo \$! > /tmp/probe_$T.pid)"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "mkdir -p $LT && cp $W/$O/logger_topics.txt $LT/logger_topics.txt" >/dev/null 2>&1
env $OPS CAND_ROOT=$W/logs/ugv/stage5/tiles_v2c1 CAND_N500=160 CAND_N499=0 CAND_PAT=stage5/tiles_v2c1/ CAND_NC=160 UGV_MAX_SPEED_KMH=20 GZ_REC_MODEL=adair_ugv_1 UGV_MODEL_VARIANT=susp_a_acc3_imu500 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2c1 WORLD=ab_route_v1 UGV_LAT_ACCEL=1.0 \
  bash logs/ugv/stage4/run_sc_v12.sh $T $TA/segB_spawn.txt $TA/segB_fleet.json bash $O/testcmd_v3.sh $T >> $O/run.out 2>&1
RC=$?
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "kill -TERM \$(cat /tmp/detail_$T.pid) 2>/dev/null; sleep 2; kill \$(cat /tmp/probe_$T.pid) 2>/dev/null; pgrep -af 'gz sim|bin/px4' | grep -v pgrep | wc -l" > $O/residual_after_$T.txt 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "rm -f $LT/logger_topics.txt && rmdir $LT 2>/dev/null; true" >/dev/null 2>&1
echo "$T run rc=$RC rcfile=$(cat logs/ugv/stage4/rc_$T.json 2>/dev/null) aabb=$(cat logs/ugv/stage4/aabb_$T.json 2>/dev/null)" >> $O/run.out
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-1/log/*/*.ulg | head -1" > $O/ulog_$T.txt 2>&1
U=$(tr -d '\r' < $O/ulog_$T.txt | tail -1)
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$O/e4_ulog_dump_v2.py "$U" $W/$O/ulog_v2_$T.json >> $O/dump.out 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$O/imu_rate_check.py "$U" $W/$O/imu_rate_$T.json >> $O/dump.out 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$TA/screen_ground.py $W/logs/ugv/stage5/tiles_v2 $W/logs/ugv/stage6/diag7/gzrec_$T $W/$O/ground_$T.json >> $O/dump.out 2>&1
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage6/slope_report.py --prefix tb3_ --logs $HK/logs/ugv --out $M/$O/tb3_slope_report.json > $O/tb3_slope_report.out 2>&1
E4_SR=tb3_slope_report.json PYTHONIOENCODING=utf-8 $PY $O/envB_judge.py > $O/judge.out 2>&1
PYTHONIOENCODING=utf-8 $PY $O/envB_extra.py $T > $O/extra.out 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$O/detail_check_v2.py $W/logs/ugv/stage5/tiles_v2 $W/$O $T > $O/detail_check.out 2>&1
S=$(grep "^$T " $O/judge.out | awk '{print $2}'); X=$(grep "^$T " $O/extra.out | awk '{print $2}'); DT=$(head -1 $O/detail_check.out | awk '{print $2}')
echo "ENVALL_RESULT $T judge=$S extra=$X detail=$DT rc=$RC $(date +%T)" >> $O/run.out
echo "CHAIN_ENVALL_DONE $(date) judge=$S extra=$X detail=$DT rc=$RC — 오퍼스 보고 (자동 후속 없음)"
