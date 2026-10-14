#!/usr/bin/env bash
# run_drive_v2 (2026-10-13, S1·S3 독립 검증 P2 반영): run_drive.sh 의 종료·증거 검사 결함 보완. 평탄 월드, PX4 미션 직접 (서버 없음).
#   bash logs/ugv/stage6/run_drive_v2.sh <후보>:<월드>:<시나리오>:<회차>[:<모델>] ...   (모델 adair_firetruck → 태그 앞 ft-, 스폰 z 0.05)
# 회차마다 (run_sc_v5 와 같은 순서):
#  1) 사전 정지 → stop_pre_<TAG>.json 이 rc=0·residual_own 0·still_alive 0 이 아니면 시험 안 함 (<TAG>.contaminated)
#  2) 기동 (ADAIR_RUN_ID=<TAG>) — CONTAMINATED·기동 실패면 시험 안 함 (<TAG>.invalid)
#  3) 실행 출처 prov_<TAG>.json (run_provenance: 이 실행 ID 의 PX4 환경으로 해석한 model.sdf 해시·Gazebo 관절) +
#     verify_drive_evidence.py: 후보 모델 내용 해시·airframe 해시·prismatic 수가 후보 파일과 같아야 함 — 아니면 시험 안 함 (<TAG>.invalid_evidence)
#  4) 주행 (drive_test --detail) — 종료 코드 ≠ 0 이거나 결과 JSON 없음이면 <TAG>.invalid_record
#  5) 로그 복사 → 사후 정지 → stop_post_<TAG>.json 이 rc=0·잔존 0 이 아니면 <TAG>.invalid_stop
# RUN_DRIVE_DONE 은 '묶음 끝'일 뿐 '모든 회차 유효'가 아니다. 무효 표시가 있는 회차는 판정에서 뺀다.
cd "$(dirname "$0")/../../../../ADAIR_wt_vehicle"
V=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle
OUT=../ADAIR/logs/ugv/stage6/drive; mkdir -p $OUT
PY=../ADAIR/.venv/Scripts/python.exe
for spec in "$@"; do
  IFS=: read -r VAR WNAME SC REP MDL <<< "$spec"
  MDL=${MDL:-adair_ugv}; PZ=0.40; PFX=""; [ "$MDL" = adair_firetruck ] && { PZ=0.05; PFX="ft-"; }
  TAG="${PFX}${VAR}_${WNAME}_${SC}_${REP:-a}"
  rm -f $OUT/$TAG.contaminated $OUT/$TAG.invalid $OUT/$TAG.invalid_evidence $OUT/$TAG.invalid_record $OUT/$TAG.invalid_stop
  WF=$V/ugv/gazebo/worlds/$WNAME.sdf; [ -f "ugv/gazebo/worlds/test/$WNAME.sdf" ] && WF=$V/ugv/gazebo/worlds/test/$WNAME.sdf
  case $SC in straight|straight50|brake) TS=200 ;; cancel*|estop*) TS=170 ;; stop30) TS=90 ;; *) TS=70 ;; esac
  echo "== $TAG $(date +%T)"
  # 1) 사전 정지·검사
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd $V && STOP_STRICT=1 bash ugv/tools/px4-stop.sh --params >/dev/null; echo rc=\$?; cat ~/.adair-ugv/stop_last.json" > $OUT/stop_pre_$TAG.txt 2>&1
  tr -d '\r' < $OUT/stop_pre_$TAG.txt | grep '^{' > $OUT/stop_pre_$TAG.json
  if ! grep -q '^rc=0' <(tr -d '\r' < $OUT/stop_pre_$TAG.txt) || ! grep -q '"residual_own":0,"still_alive":0' $OUT/stop_pre_$TAG.json; then
    echo "  앞 실행 잔존 — 시험 안 함: $(tr -d '\r' < $OUT/stop_pre_$TAG.txt | paste -sd' ')" | tee $OUT/$TAG.contaminated; continue
  fi
  # 2) 기동
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd $V && ADAIR_RUN_ID=$TAG UGV_MODEL_VARIANT=$VAR WORLD=$WNAME WORLD_FILE=$WF MODEL=$MDL INSTANCE=1 POSE=0,0,$PZ,0 bash ugv/tools/px4-start.sh > /tmp/start_$TAG.log 2>&1; r=\$?; tail -3 /tmp/start_$TAG.log; echo start_rc=\$r" > $OUT/${TAG}_start.txt 2>&1
  if grep -q "CONTAMINATED\|뜨지 않음\|없음" $OUT/${TAG}_start.txt || ! grep -q '^start_rc=0' <(tr -d '\r' < $OUT/${TAG}_start.txt); then
    echo "  기동 실패/오염 — 시험 안 함: $(tr -d '\r' < $OUT/${TAG}_start.txt | tail -2 | paste -sd' ')" | tee $OUT/$TAG.invalid
    MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd $V && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"; continue
  fi
  # 3) 실행 출처·증거 검사
  printf '1 %s 0,0,%s,0 %s_1\n' "$MDL" "$PZ" "$MDL" > $OUT/spawn_$TAG.txt
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --cd "$V" --exec python3 -m ugv.tools.run_provenance --run-id "$TAG" --spawn "$V/../ADAIR/logs/ugv/stage6/drive/spawn_$TAG.txt" --out "$V/../ADAIR/logs/ugv/stage6/drive/prov_$TAG.json" > $OUT/prov_$TAG.txt 2>&1
  if ! PYTHONIOENCODING=utf-8 $PY ../ADAIR/logs/ugv/stage6/verify_drive_evidence.py $OUT/prov_$TAG.json $VAR $MDL "$(git rev-parse --short HEAD)$(git status --porcelain | grep -qv '^??' && echo -dirty)" > $OUT/verify_$TAG.txt 2>&1; then
    echo "  증거 검사 실패 — 시험 안 함: $(tail -1 $OUT/verify_$TAG.txt)" | tee $OUT/$TAG.invalid_evidence
    MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd $V && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"; continue
  fi
  sleep 20   # EKF 높이 추정 안정 (2026-10-12 시험: 8 s 에서 arm 거부 "height estimate not stable")
  # 4) 주행
  UGV_GZ_PARTITION=adair_ugv PYTHONIOENCODING=utf-8 $PY -m ugv.tools.drive_test $SC --world $WNAME --detail --tag $TAG --track-s $TS --model ${MDL}_1 > $OUT/$TAG.out 2>&1
  RC=$?
  echo "  rc=$RC $(grep -o '"[a-z_]*speed[a-z_]*": [0-9.]*' $OUT/$TAG.out | head -3 | paste -sd' ')"
  mv logs/ugv/${TAG}_* $OUT/ 2>/dev/null
  if [ $RC -ne 0 ] || ! ls $OUT/${TAG}_2*[0-9].json >/dev/null 2>&1; then
    echo "주행 도구 실패 또는 결과 JSON 없음 (rc=$RC): $(tail -2 $OUT/$TAG.out | paste -sd' ')" | tee $OUT/$TAG.invalid_record
  fi
  # 5) 로그 복사 → 사후 정지·검사
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cp ~/.adair-ugv/px4-1.log $V/../ADAIR/logs/ugv/stage6/drive/${TAG}_px4.log 2>/dev/null; cd $V && STOP_STRICT=1 bash ugv/tools/px4-stop.sh >/dev/null; echo rc=\$?; cat ~/.adair-ugv/stop_last.json" > $OUT/stop_post_$TAG.txt 2>&1
  tr -d '\r' < $OUT/stop_post_$TAG.txt | grep '^{' > $OUT/stop_post_$TAG.json
  cp $OUT/stop_post_$TAG.json $OUT/${TAG}_stop.json 2>/dev/null
  if ! grep -q '^rc=0' <(tr -d '\r' < $OUT/stop_post_$TAG.txt) || ! grep -q '"still_alive":0' $OUT/stop_post_$TAG.json || ! grep -q '"residual_own":0' $OUT/stop_post_$TAG.json; then
    echo "  사후 종료 확인 실패: $(tr -d '\r' < $OUT/stop_post_$TAG.txt | paste -sd' ')" | tee $OUT/$TAG.invalid_stop
  fi
done
echo "RUN_DRIVE_DONE $(date)"
