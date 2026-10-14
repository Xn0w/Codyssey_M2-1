#!/usr/bin/env bash
# 2026-10-12 차량 개조 검증 P1 S3(요철)·P3 T1~T4(60 km/h 직선·가속·제동, 30 km/h 정지) — 평탄 월드, PX4 미션 직접 (서버 없음).
#   bash logs/ugv/stage6/run_drive.sh <후보>:<월드>:<시나리오>:<회차>[:<모델>] ...   (모델 adair_firetruck → 태그 앞 ft-, 스폰 z 0.05)
# 기동·종료 = ADAIR_wt_vehicle px4-start/stop (프로세스 기록·실행 오염 거부), 주행·기록 = ADAIR_wt_vehicle ugv.tools.drive_test (--detail, gz_detail)
cd "$(dirname "$0")/../../../../ADAIR_wt_vehicle"
V=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle
OUT=../ADAIR/logs/ugv/stage6/drive; mkdir -p $OUT
PY=../ADAIR/.venv/Scripts/python.exe
for spec in "$@"; do
  IFS=: read -r VAR WNAME SC REP MDL <<< "$spec"
  MDL=${MDL:-adair_ugv}; PZ=0.40; PFX=""; [ "$MDL" = adair_firetruck ] && { PZ=0.05; PFX="ft-"; }
  TAG="${PFX}${VAR}_${WNAME}_${SC}_${REP:-a}"
  WF=$V/ugv/gazebo/worlds/$WNAME.sdf; [ -f "ugv/gazebo/worlds/test/$WNAME.sdf" ] && WF=$V/ugv/gazebo/worlds/test/$WNAME.sdf
  case $SC in straight|straight50|brake) TS=200 ;; stop30) TS=90 ;; *) TS=70 ;; esac
  echo "== $TAG $(date +%T)"
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd $V && STOP_STRICT=1 bash ugv/tools/px4-stop.sh --params >/dev/null; echo pre_stop_rc=\$?; ADAIR_RUN_ID=$TAG UGV_MODEL_VARIANT=$VAR WORLD=$WNAME WORLD_FILE=$WF MODEL=$MDL INSTANCE=1 POSE=0,0,$PZ,0 bash ugv/tools/px4-start.sh 2>&1 | tail -3" > $OUT/${TAG}_start.txt 2>&1
  if grep -q "CONTAMINATED\|뜨지 않음\|없음" $OUT/${TAG}_start.txt; then echo "  기동 실패/오염 — 무효: $(tail -1 $OUT/${TAG}_start.txt)"; touch $OUT/$TAG.invalid; continue; fi
  sleep 20   # EKF 높이 추정 안정 (2026-10-12 시험: 8 s 에서 arm 거부 "height estimate not stable")
  UGV_GZ_PARTITION=adair_ugv PYTHONIOENCODING=utf-8 $PY -m ugv.tools.drive_test $SC --world $WNAME --detail --tag $TAG --track-s $TS --model ${MDL}_1 > $OUT/$TAG.out 2>&1
  echo "  rc=$? $(grep -o '"[a-z_]*speed[a-z_]*": [0-9.]*' $OUT/$TAG.out | head -3 | paste -sd' ')"
  mv logs/ugv/${TAG}_* $OUT/ 2>/dev/null
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd $V && cp ~/.adair-ugv/px4-1.log ../ADAIR/logs/ugv/stage6/drive/${TAG}_px4.log 2>/dev/null; STOP_STRICT=1 bash ugv/tools/px4-stop.sh; cp ~/.adair-ugv/stop_last.json ../ADAIR/logs/ugv/stage6/drive/${TAG}_stop.json"
done
echo "RUN_DRIVE_DONE $(date)"
