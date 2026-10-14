#!/usr/bin/env bash
# A 재실행 시험 명령 v3 (Codex 1000): 고율 기록기 생명주기·준비·감시 게이트. run_sc_v11_c1 가 ADAIR 루트에서 실행. 종료 코드: road_test rc, 11 = 준비 실패 (미션 안 보냄), 12 = 주행 중 감시 실패 (road_test 종료 → 래퍼 사후 정지).
# 1) 기록기 = Windows 쪽 백그라운드 wsl.exe 세션의 전면 프로세스 (세션이 살아 있는 동안 유지; WPID = 그 wsl.exe), --heartbeat 1 s.
# 2) 준비 (정지 스폰, 최대 30 s): 상태 파일 두 번 이상에서 last_sim 증가, 행 ≥ 20, 네 바퀴 마지막 접촉 VALID, 서스펜션 q 4 개 유한 → detail_ready_<T>.json. 아니면 기록기 종료·11.
# 3) 감시 (road_test 동안 2 s 마다): wsl.exe 생존, 상태 파일 wall 나이 ≤ 5 s, last_sim 이 6 s 안에 증가, 중단 신호 없음. 아니면 road_test 종료 (래퍼의 검증된 사후 정지가 이어짐) → detail_watchdog_<T>.json·12.
# 4) road_test 끝 → 기록기 (자기 pid) SIGTERM → 메타·종료 코드 기록. PX4/Gazebo/다른 기록기는 건드리지 않음.
T=$1; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR; O=logs/ugv/stage6/terrain_ab/envAll
M=$(pwd); ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe; HK=../ADAIR_wt_hook; SUB=$ST/tiles_v2c1/road_subset_ab_route_v1.json
HB=$O/detail_hb_$T.json; rm -f $HB
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec env GZ_PARTITION=adair_ugv GZ_IP=127.0.0.1 python3 $W/$O/gz_detail_seam_v2.py --world ab_route_v1 --model adair_ugv_1 \
  --out $W/$O/detail_$T.csv --duration 600 --heartbeat $W/$HB > $O/detail_$T.log 2>&1 &
WPID=$!; echo "detail_wsl_pid=$WPID start=$(date +%T)" > $O/detail_life_$T.txt
hb() { $PY -c "import json,sys,math
try: h=json.load(open(sys.argv[1]))
except Exception: print('NOHB'); sys.exit()
import time
ok_states=all(v=='VALID' for v in h['states_last'].values()); ok_q=all(isinstance(v,(int,float)) and math.isfinite(v) for v in h['susp_q_last'].values())
print(h['pid'], h['rows'], h['last_sim'], round(time.time()-h['wall'],2), int(ok_states), int(ok_q), 1 if (h['abort'] or {}).get('reason') else 0)" $HB 2>/dev/null; }
READY=0; PREV=""
for i in $(seq 30); do
  sleep 1; kill -0 $WPID 2>/dev/null || break
  H=$(hb); [ "$H" = NOHB ] || [ -z "$H" ] && continue
  set -- $H; LPID=$1; ROWS=$2; SIM=$3; AGE=$4; OKS=$5; OKQ=$6; AB=$7
  if [ -n "$PREV" ] && [ "$SIM" != "$PREV" ] && [ "$ROWS" -ge 20 ] && [ "$OKS" = 1 ] && [ "$OKQ" = 1 ] && [ "$AB" = 0 ]; then READY=1; break; fi
  PREV=$SIM
done
echo "{\"ready\":$READY,\"hb\":\"$H\",\"waited_s\":$i}" > $O/detail_ready_$T.json
if [ $READY != 1 ]; then
  echo "고율 기록기 준비 실패 ($H) — 미션 안 보냄"; MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "kill -TERM ${LPID:-0} 2>/dev/null"; sleep 2; kill $WPID 2>/dev/null; exit 11
fi
( cd $HK && exec env UGV_MAX_SPEED_KMH=20 UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2c1 $PY -m ugv.tools.road_test --tag $T --rid A-ugv1 --model adair_ugv_1 --target 38.06325574385999 128.17025179536637 --track-s 240 --post-stop-s 35 --world ab_route_v1 ) &
RT=$!   # exec 로 서브셸이 road_test 자체가 됨 → kill $RT 가 road_test 를 끝냄
LAST_SIM=""; LAST_CHANGE=$(date +%s); WD=""
while kill -0 $RT 2>/dev/null; do
  sleep 2
  kill -0 $WPID 2>/dev/null || { WD="RECORDER_EXITED"; break; }
  H=$(hb); [ "$H" = NOHB ] && { WD="NO_HEARTBEAT"; break; }
  set -- $H; SIM=$3; AGE=$4; AB=$7
  awk "BEGIN{exit !($AGE > 5)}" && { WD="HEARTBEAT_STALE age=$AGE"; break; }
  [ "$AB" = 1 ] && { WD="RECORDER_ABORT_SIGNAL"; break; }
  if [ "$SIM" != "$LAST_SIM" ]; then LAST_SIM=$SIM; LAST_CHANGE=$(date +%s); elif [ $(( $(date +%s) - LAST_CHANGE )) -gt 6 ]; then WD="SIM_NOT_ADVANCING"; break; fi
done
if [ -n "$WD" ]; then
  echo "{\"watchdog\":\"$WD\",\"hb\":\"$H\",\"time\":\"$(date +%T)\"}" > $O/detail_watchdog_$T.json
  echo "감시 실패 ($WD) — road_test 종료"; kill $RT 2>/dev/null; sleep 3
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "kill -TERM $LPID 2>/dev/null"; sleep 3; kill $WPID 2>/dev/null; exit 12
fi
wait $RT; RTRC=$?
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "kill -TERM $LPID 2>/dev/null"
for i in $(seq 15); do kill -0 $WPID 2>/dev/null || break; sleep 1; done
wait $WPID 2>/dev/null; echo "detail_rc=$? road_test_rc=$RTRC end=$(date +%T)" >> $O/detail_life_$T.txt
exit $RTRC
