#!/usr/bin/env bash
# 2026-10-13 S3 fire_v2b 검증 (S3 문서 8절, 결과 전 고정): 뒤축 설정 강성 한 항목만 실측 기반 보정한 fire_v2b.
#   시작 조건: chain_s4i 끝 + fire_v2b 준비 표식(logs/ugv/stage6/fire_v2b_ready — 뒤축 실측·후보 생성·해시 확인 뒤 수동 생성)
#   정적: 평지·뒤 판 2/5 cm·앞 판 2/5 cm / 주행: 요철 4·회전 3 (CG 1.2 m, 정차 정책 server). 기준 불변.
cd "$(dirname "$0")/../../.."
until grep -q CHAIN_S4I_DONE logs/ugv/stage6/chain_s4i.out 2>/dev/null && [ -f logs/ugv/stage6/fire_v2b_ready ]; do sleep 30; done
F=adair_firetruck
# 코드 커밋 게이트 (후속 계획 9313aee 재검토 2): 조회 실패·빈 값이면 기동 전에 거부. 전체 커밋 ID + 수정 여부 별도 기록
VTC_FULL=$(git -C ../ADAIR_wt_vehicle rev-parse HEAD 2>/dev/null)
if [ -z "$VTC_FULL" ] || [ ${#VTC_FULL} -ne 40 ]; then echo "CHAIN_FT4_REFUSED $(date) 차량 트리 커밋 조회 실패 — 시험 안 함"; exit 1; fi
VDIRTY=$(git -C ../ADAIR_wt_vehicle status --porcelain --untracked-files=no | wc -l)
VTC="$VTC_FULL$([ "$VDIRTY" != 0 ] && echo -dirty)"
echo "{\"vehicle_tree_commit\": \"$VTC_FULL\", \"dirty_files\": $VDIRTY, \"susp_static_test_sha1\": \"$(sha1sum ../ADAIR_wt_vehicle/ugv/tools/susp_static_test.sh | cut -c1-40)\", \"gz_detail_sha1\": \"$(sha1sum ../ADAIR_wt_vehicle/ugv/tools/gz_detail.py | cut -c1-40)\", \"verify_sha1\": \"$(sha1sum logs/ugv/stage6/verify_drive_evidence.py | cut -c1-40)\"}" > logs/ugv/stage6/ft4_code_manifest.json
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle && VEHICLE_TREE_COMMIT=$VTC bash ugv/tools/susp_static_test.sh ../ADAIR/logs/ugv/stage6/susp_static_ft4 fire_v2b:adair_flat_susp:60:$F fire_v2b:adair_flat_diag2ft2r:60:$F fire_v2b:adair_flat_diag5ft2r:60:$F fire_v2b:adair_flat_diag2ft2:60:$F fire_v2b:adair_flat_diag5ft2:60:$F" > logs/ugv/stage6/static_ft4.out 2>&1
# 물리 엔진 증거 (DART 설치 버전·gz 버전·월드 물리 시간 간격)
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "gz sim --version 2>/dev/null | head -2; dpkg -l 2>/dev/null | grep -iE 'dart|gz-physics' | awk '{print \$2, \$3}' | head -8; grep -h max_step_size /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle/ugv/gazebo/worlds/test/adair_flat_susp.sdf /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle/ugv/gazebo/worlds/adair_flat.sdf | head -2" > logs/ugv/stage6/ft4_physics_versions.txt 2>&1
# 중간 게이트: 정적 회차를 S3 9절 예측과 대조 — 크게 어긋나면 주행 보류 (원인 분석 뒤 소유자가 판단)
(cd ../ADAIR_wt_vehicle && PYTHONIOENCODING=utf-8 ../ADAIR/.venv/Scripts/python.exe -m ugv.tools.susp_static_report ../ADAIR/logs/ugv/stage6/susp_static_ft4 --out ../ADAIR/logs/ugv/stage6/susp_static_ft4/report_ssr2.json > ../ADAIR/logs/ugv/stage6/susp_static_ft4/report.txt 2>&1)
if ! PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe logs/ugv/stage6/ft4_gate.py > logs/ugv/stage6/ft4_gate.out 2>&1; then
  echo "CHAIN_FT4_HOLD $(date) 정적 회차가 예측 범위 밖 또는 무효 — 주행 보류: $(tail -1 logs/ugv/stage6/ft4_gate.out)"
  echo "CHAIN_FT4_DONE $(date) (주행 보류, 정적만)"; exit 0
fi
export UGV_DRIVE_PARK=server
bash logs/ugv/stage6/run_drive_v2c.sh fire_v2b:adair_flat_susp:bump:a:$F fire_v2b:adair_flat_susp:bump:b:$F fire_v2b:adair_flat_susp:bump:c:$F fire_v2b:adair_flat_susp:bump:d:$F \
  fire_v2b:adair_flat:curve:a:$F fire_v2b:adair_flat:curve:b:$F fire_v2b:adair_flat:curve:c:$F > logs/ugv/stage6/drive_ft4.out 2>&1
echo "CHAIN_FT4_DONE $(date)"
