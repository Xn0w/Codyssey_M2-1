#!/usr/bin/env bash
# (전 타일 보정 월드 tiles_v2c1 사본: AABB 160/0·prov 160) # (B 단계 4 타일 사본: 후보 루트 seamB4/tiles_c1b4, AABB 500×4·499.512×156, prov 후보 dir 4) # seam_static_c1.sh — 후보 c1 (T04_16·T05_16 충돌 size 보정 사본) 정지 재현 (Codex 0920, 기준 SEAMC_criteria.md). seam_static.sh 와 차이: 모델 검색 = 후보 루트 먼저 + 원본 tiles_v2, 기동 뒤 AABB 증거 (반폭 500.000 = 2 줄, 499.512 = 158 줄) 아니면 invalid_evidence. ADAIR_wt_vehicle/ugv/tools/susp_static_test.sh 사본 기반:
# 월드 = tiles_v2/ab_route_v1.sdf (160 타일, 원본 그대로), 모델 검색 tiles_v2, 차량 susp_a_acc3_imu500, NO_PX4=1 (구동 명령 없음 — JointController 0),
# 스폰 x,y,z,yaw 만 회차별, 기록기 = gz_detail_seam.py (바퀴별 접촉 상대·점·깊이, 0.3 s 중단 신호), gz 로그 verbose 4 (높이장 AABB 디버그).
#   bash seam_static.sh <출력 폴더(절대)> <TAG>:<x,y,z,yaw>:<기록 s> ...
set -u
CAND=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/logs/ugv/stage5/tiles_v2c1; V=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle; A=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR; TL=$A/logs/ugv/stage5/tiles_v2c1
OUT="$1"; shift; mkdir -p "$OUT"; HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; SC=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/logs/ugv/stage6/terrain_ab/seamC
export STATE_DIR="$HOME/.adair-susptest" GZ_PARTITION=adair_susptest GZ_IP=127.0.0.1
for spec in "$@"; do
  IFS=: read -r TAG P DUR <<< "$spec"
  echo "== $TAG pose $P (기록 ${DUR} s)"
  rm -f "$OUT/$TAG".{contaminated,invalid,invalid_evidence,invalid_stop,abort}
  STOP_STRICT=1 bash "$V/ugv/tools/px4-stop.sh" >/dev/null; rc=$?
  cp "$STATE_DIR/stop_last.json" "$OUT/stop_pre_$TAG.json" 2>/dev/null
  if [ "$rc" != 0 ] || ! grep -q '"residual_own":0,"still_alive":0' "$OUT/stop_pre_$TAG.json" 2>/dev/null; then
    echo "  앞 실행 잔존 — 시험 안 함 (rc $rc)" | tee "$OUT/$TAG.contaminated"; continue
  fi
  ADAIR_RUN_ID="$TAG" NO_PX4=1 UGV_MODEL_VARIANT=susp_a_acc3_imu500 WORLD=ab_route_v1 WORLD_FILE="$TL/ab_route_v1.sdf" GZ_SIM_RESOURCE_PATH="$CAND:$TL" \
    MODEL=adair_ugv INSTANCE=1 POSE="$P" GZ_VERBOSE=4 bash "$V/ugv/tools/px4-start.sh" | tail -2
  rc=${PIPESTATUS[0]}
  if [ "$rc" != 0 ]; then echo "  기동 실패 (rc $rc) — 무효" | tee "$OUT/$TAG.invalid"; bash "$V/ugv/tools/px4-stop.sh" >/dev/null 2>&1; continue; fi
  printf '1 adair_ugv %s adair_ugv_1\n' "$P" > "$OUT/spawn_$TAG.txt"
  ( cd "$V" && python3 -m ugv.tools.run_provenance --run-id "$TAG" --spawn "$OUT/spawn_$TAG.txt" --out "$OUT/prov_$TAG.json" ) > "$OUT/prov_$TAG.txt" 2>&1
  sleep 3
  N500=$(grep -cE "Heightfield AABB: min = \{-500(\.0+)?, -500(\.0+)?," "$STATE_DIR/gz-server.log"); N499=$(grep -cE "Heightfield AABB: min = \{-499\.512, -499\.512," "$STATE_DIR/gz-server.log")
  echo "{\"aabb_500\":$N500,\"aabb_499_512\":$N499}" > "$OUT/aabb_$TAG.json"
  if [ "$N500" != 160 ] || [ "$N499" != 0 ]; then
    echo "  후보 해석 증거 실패 (AABB 500=$N500, 499.512=$N499) — 시험 안 함" | tee "$OUT/$TAG.invalid_evidence"; bash "$V/ugv/tools/px4-stop.sh" >/dev/null 2>&1; continue
  fi
  NC=$(python3 -c "import json,sys;p=json.load(open(sys.argv[1]));print(sum(1 for t in p['world']['tiles'] if 'stage5/tiles_v2c1/' in t['dir']))" "$OUT/prov_$TAG.json" 2>/dev/null || echo 0)
  echo "{\"prov_candidate_tiles\":$NC}" > "$OUT/provc_$TAG.json"
  if [ "$NC" != 160 ]; then echo "  후보 해석 증거 실패 (prov 후보 dir $NC) — 시험 안 함" | tee "$OUT/$TAG.invalid_evidence"; bash "$V/ugv/tools/px4-stop.sh" >/dev/null 2>&1; continue; fi
  if ! python3 "$A/logs/ugv/stage6/verify_drive_evidence.py" "$OUT/prov_$TAG.json" susp_a_acc3_imu500 adair_ugv "${VEHICLE_TREE_COMMIT:-unknown}" > "$OUT/verify_$TAG.txt" 2>&1; then
    echo "  증거 검사 실패 — 시험 안 함: $(tail -1 "$OUT/verify_$TAG.txt")" | tee "$OUT/$TAG.invalid_evidence"; bash "$V/ugv/tools/px4-stop.sh" >/dev/null 2>&1; continue
  fi
  python3 "$SC/gz_detail_seam.py" --world ab_route_v1 --model adair_ugv_1 --out "$OUT/$TAG.csv" --duration "$DUR" > "$OUT/${TAG}_gz_detail.log" 2>&1
  GRC=$?; echo "gz_detail_rc=$GRC" >> "$OUT/${TAG}_gz_detail.log"; tail -2 "$OUT/${TAG}_gz_detail.log"
  if [ "$GRC" = 5 ]; then echo "  중단 신호 — 회차 종료·보존: $(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['abort'])" "$OUT/${TAG}_meta.json")" | tee "$OUT/$TAG.abort"
  elif [ "$GRC" != 0 ]; then echo "  기록기 비정상 종료 (rc $GRC) — 무효" | tee "$OUT/$TAG.invalid"; fi
  cp "$STATE_DIR/gz-server.log" "$OUT/${TAG}_gz-server.log" 2>/dev/null
  STOP_STRICT=1 bash "$V/ugv/tools/px4-stop.sh"; rc=$?
  cp "$STATE_DIR/stop_last.json" "$OUT/${TAG}_stop.json"
  if [ "$rc" != 0 ] || ! grep -q '"still_alive":0' "$OUT/${TAG}_stop.json" || ! grep -q '"residual_own":0' "$OUT/${TAG}_stop.json"; then
    echo "  사후 종료 확인 실패 (rc $rc)" | tee "$OUT/$TAG.invalid_stop"
  fi
done
echo "SEAM_STATIC_DONE $(date)"
