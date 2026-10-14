# A 단계 장부 (Codex 1020 2·3)
- tb2_segB_c1_a: UNCONFIRMED (고율 기록기 출력 0, 기동/준비 검사 결함) — 보존, 유효 회차 아님.
- tb2_segB_c1_b: 실제 실행 시각 (원본) — 기록기 life 09:50:18~09:53:02, 래퍼 rc 파일 09:53:09, 체인 결과 줄 09:53:15. ('10:10/10:20 보고' 는 opus_to_codex 항목 라벨이며 실행 시각 아님.)
  - 최초 detail_check_v2 출력 (detail_check_ORDERBUG_*.out/json): coverage_to_hold = null → UNCONFIRMED. 원인 = chain_envB_c1b.sh 가 slope_report 보다 detail_check 를 먼저 호출 (원본 체인·동결표 그대로 보존).
  - 정정 분석: `wsl python3 detail_check_v2.py <tiles_v2> <envB_c1> tb2_segB_c1_b` (slope_report 생성 뒤, 같은 판정기 sha1 = ENVB_C1B_freeze 의 detail_check_v2.py, 같은 물리 기록) → PASS. 입력 tb2_slope_report.json (tb2_segB_c1_b hold.confirm_sim_t 143.888).
  - 기록기 rc 3 = road_test 정상 종료 뒤 자기 pid SIGTERM (계획된 종료, meta abort null, 범위 238.656). rc 3 을 일반 정상으로 허용하는 규칙은 만들지 않음.
- 후속 체인 (B 부터): 수집 끝·출력 확인 → (보고서) → 판정 → 판정 출력 확인 → 합성 순서, 의존 파일 없으면 MISSING/NO_JUDGE 로 멈춤 (이전 회차 파일 재사용 안 함).
