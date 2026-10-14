#!/usr/bin/env bash
# 2026-10-13 후속 계획 S4 7.1(평지 회전 선별)·7.3(소방차 무게중심 높이 민감도 1.0~1.4 m, S2 문서에서 결과 전 고정). chain_s4 뒤에.
#  curve = drive_test 90°·45°·135° 꺾임 경로 (평지, 추정 도로 폭 판정 아님 — 실제 도로 회전 선별은 S5 프로필 통합 뒤)
#  fire_v2_cg100 / fire_v2_cg140 = fire_v2 와 차체 관성 중심 높이만 다름 (1.0 / 1.4 m, fire_v2 1.2 m) — 회전·비상 정지 50 각 3회
cd "$(dirname "$0")/../../.."
export UGV_DRIVE_PARK=server
until grep -q CHAIN_S4P_DONE logs/ugv/stage6/chain_s4p.out 2>/dev/null; do sleep 30; done
F=adair_firetruck
bash logs/ugv/stage6/run_drive_v2c.sh \
  fire_v2:adair_flat:curve:a:$F fire_v2:adair_flat:curve:b:$F fire_v2:adair_flat:curve:c:$F \
  fire_v2_cg100:adair_flat:curve:a:$F fire_v2_cg100:adair_flat:curve:b:$F fire_v2_cg100:adair_flat:curve:c:$F \
  fire_v2_cg140:adair_flat:curve:a:$F fire_v2_cg140:adair_flat:curve:b:$F fire_v2_cg140:adair_flat:curve:c:$F \
  fire_v2_cg100:adair_flat:estop50:a:$F fire_v2_cg100:adair_flat:estop50:b:$F fire_v2_cg100:adair_flat:estop50:c:$F \
  fire_v2_cg140:adair_flat:estop50:a:$F fire_v2_cg140:adair_flat:estop50:b:$F fire_v2_cg140:adair_flat:estop50:c:$F \
  susp_a:adair_flat:curve:a susp_a:adair_flat:curve:b susp_a:adair_flat:curve:c \
  > logs/ugv/stage6/drive_s4b.out 2>&1
echo "CHAIN_S4B_DONE $(date)"
