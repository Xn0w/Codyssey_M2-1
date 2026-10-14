# B 정확-경계 v3 재기록 1 회 — 사전 기준 (2026-10-14, 실행 전, Codex 1055)
- 목적: 원 bR1y (FAIL, 점별 원본 없음) 와 **같은 배치** (중심 15400.8, −4632.35, z 101.992, yaw π/2 → 앞바퀴 y −4631.000)·같은 4 타일 후보·차량·엔진/step·NO_PX4 무구동·센서·정착/중단 규칙. **바뀐 것 = 기록기 v3 (점별 원본 JSONL) 와 래퍼 사본 seam_static_b4d.sh** 뿐. 새 ID b4e_exact. 원 bR1y 출력 보존.
- 판정 seam_check_c1b.py (기존 기준 그대로) + raw_check_v2.py (판정 없음): 점별 법선 방향/기울기·위치·depth·상대, 엔진 body 이름 (비어 있으면 그 사실 기록 — +z 추론은 참고로만), 작용반작용 f1+f2, 앞바퀴 축 방향 순힘, 정착 뒤 바퀴 link 위치 (명목 vs 실제 경계 배치), 서스펜션 q·조향·바퀴 회전.
- 비교 대상: bD_N·bD_S (같은 sim 표본 규약). raw_check_v2 로 bD_N 도 재분석 (rawcheck_b4d_N.json 이 v2 상위 출력으로 바뀜 — v1 원 출력은 docs/ugv/evidence/terrain_seamB4_20261014/runs_d 에 보존).
- 해석 규칙: 같은 힘 이상 재현 또는 집계 ratio 와 점별 힘/법선 차이를 설명 못 함 → 기존 Fable 검토 재개 요청. 이상 미재현이어도 원 FAIL 과의 차이를 설명하기 전 정적 게이트 닫지 않음. 회차 반복 없음. bR2y·bR1c HOLD.
