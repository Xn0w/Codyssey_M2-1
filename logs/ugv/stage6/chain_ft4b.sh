#!/usr/bin/env bash
# 2026-10-13 fire_v2b 마무리 (사용자 지시: 서스펜션 검증을 개선 비교보다 먼저). chain_slope2 뒤, chain_slope3 앞.
#  1) ft4 1차에서 기록기 종료 중단(rc 134, CSV 는 완전)으로 무효였던 5 cm 앞판 1회 재시험 (기록기 종료 수정 e6adbb5 뒤). 무효 회차 파일은 susp_static_ft4/invalid_run1_diag5ft2/ 보존
#  2) 게이트 ft4_gate2: 정적 필수 5회 모두 기준 PASS (불변) + 예측 일치. 5 cm 뒤판 예측 차는 원인 확인(롤 0 가정 불성립)된 경우 뒤축 Δfn/Δq 가 예측 700 kN/m ±5 % 이면 진행
#  3) 통과하면 요철 4·회전 3 (CG 1.2 m, 정차 정책 server)
cd "$(dirname "$0")/../../.."
until grep -q CHAIN_SLOPE2_DONE logs/ugv/stage6/chain_slope2.out 2>/dev/null; do sleep 30; done
F=adair_firetruck
VTC_FULL=$(git -C ../ADAIR_wt_vehicle rev-parse HEAD 2>/dev/null)
if [ -z "$VTC_FULL" ] || [ ${#VTC_FULL} -ne 40 ]; then echo "CHAIN_FT4B_REFUSED $(date) 차량 트리 커밋 조회 실패"; echo "CHAIN_FT4B_DONE $(date) (거부)"; exit 1; fi
VDIRTY=$(git -C ../ADAIR_wt_vehicle status --porcelain --untracked-files=no | wc -l)
VTC="$VTC_FULL$([ "$VDIRTY" != 0 ] && echo -dirty)"
echo "{\"vehicle_tree_commit\": \"$VTC_FULL\", \"dirty_files\": $VDIRTY, \"gz_detail_sha1\": \"$(sha1sum ../ADAIR_wt_vehicle/ugv/tools/gz_detail.py | cut -c1-40)\"}" > logs/ugv/stage6/ft4b_code_manifest.json
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle && VEHICLE_TREE_COMMIT=$VTC bash ugv/tools/susp_static_test.sh ../ADAIR/logs/ugv/stage6/susp_static_ft4 fire_v2b:adair_flat_diag5ft2:60:$F" > logs/ugv/stage6/static_ft4b.out 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "gz sim --version 2>/dev/null | head -1; dpkg -l 2>/dev/null | grep -iE 'libdart-core|libgz-physics7-dartsim' | awk '{print \$2, \$3}'" > logs/ugv/stage6/ft4_physics_versions.txt 2>&1
(cd ../ADAIR_wt_vehicle && PYTHONIOENCODING=utf-8 ../ADAIR/.venv/Scripts/python.exe -m ugv.tools.susp_static_report ../ADAIR/logs/ugv/stage6/susp_static_ft4 --out ../ADAIR/logs/ugv/stage6/susp_static_ft4/report_ssr2.json > ../ADAIR/logs/ugv/stage6/susp_static_ft4/report.txt 2>&1)
if ! PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe logs/ugv/stage6/ft4_gate2.py > logs/ugv/stage6/ft4b_gate.out 2>&1; then
  echo "CHAIN_FT4B_HOLD $(date) 게이트 미통과 — 주행 보류: $(tail -1 logs/ugv/stage6/ft4b_gate.out | cut -c1-400)"
  echo "CHAIN_FT4B_DONE $(date) (주행 보류)"; exit 0
fi
export UGV_DRIVE_PARK=server
bash logs/ugv/stage6/run_drive_v2c.sh fire_v2b:adair_flat_susp:bump:a:$F fire_v2b:adair_flat_susp:bump:b:$F fire_v2b:adair_flat_susp:bump:c:$F fire_v2b:adair_flat_susp:bump:d:$F \
  fire_v2b:adair_flat:curve:a:$F fire_v2b:adair_flat:curve:b:$F fire_v2b:adair_flat:curve:c:$F > logs/ugv/stage6/drive_ft4b.out 2>&1
echo "CHAIN_FT4B_DONE $(date)"
