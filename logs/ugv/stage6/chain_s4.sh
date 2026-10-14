#!/usr/bin/env bash
# 2026-10-13 S1·S3 독립 검증 수정 지시 R4.2(fire_v2 요철 반복성)·후속 계획 S4(명령 기준 제동: 임무 도착 / 명령 취소 / 비상 정지).
# 실행 래퍼 run_drive_v2 (사전·사후 정지 검사, 모델 해시·관절 증거, 기록 실패 표시). 평탄 월드 adair_flat / adair_flat_susp.
#  1) fire_v2 요철 b·c·d — a 회차 후륜 q 0.08013 m (기준 < 0.08 초과) 재현성 확인. 기준·모델은 바꾸지 않는다
#  2) 소방차 fire_v2: 비상 50·30, 취소 50·30, 임무 도착 30 각 3회, 임무 도착 50 c (a·b 는 chain_ft2)
#  3) UGV susp_a: 비상 60·30, 취소 60·30 각 3회, 임무 도착 30 b·c (a 는 stage6 drive)
cd "$(dirname "$0")/../../.."
F=adair_firetruck
bash logs/ugv/stage6/run_drive_v2.sh \
  fire_v2:adair_flat_susp:bump:b:$F fire_v2:adair_flat_susp:bump:c:$F fire_v2:adair_flat_susp:bump:d:$F \
  fire_v2:adair_flat:estop50:a:$F fire_v2:adair_flat:estop50:b:$F fire_v2:adair_flat:estop50:c:$F \
  fire_v2:adair_flat:estop30:a:$F fire_v2:adair_flat:estop30:b:$F fire_v2:adair_flat:estop30:c:$F \
  fire_v2:adair_flat:cancel50:a:$F fire_v2:adair_flat:cancel50:b:$F fire_v2:adair_flat:cancel50:c:$F \
  fire_v2:adair_flat:cancel30:a:$F fire_v2:adair_flat:cancel30:b:$F fire_v2:adair_flat:cancel30:c:$F \
  fire_v2:adair_flat:stop30:a:$F fire_v2:adair_flat:stop30:b:$F fire_v2:adair_flat:stop30:c:$F \
  fire_v2:adair_flat:straight50:c:$F \
  susp_a:adair_flat:estop60:a susp_a:adair_flat:estop60:b susp_a:adair_flat:estop60:c \
  susp_a:adair_flat:estop30:a susp_a:adair_flat:estop30:b susp_a:adair_flat:estop30:c \
  susp_a:adair_flat:cancel60:a susp_a:adair_flat:cancel60:b susp_a:adair_flat:cancel60:c \
  susp_a:adair_flat:cancel30:a susp_a:adair_flat:cancel30:b susp_a:adair_flat:cancel30:c \
  susp_a:adair_flat:stop30:b susp_a:adair_flat:stop30:c \
  > logs/ugv/stage6/drive_s4.out 2>&1
echo "CHAIN_S4_DONE $(date)"
