# S5 운영 조합 확인 2회 — 사전 기준 (2026-10-14 08:0x, 실행 전, Codex 0755 2절)

## 동결 (S5 후보 + 운영 예정 조합)
서버 03d5b5d, 차량 48f3e5f susp_a_acc3_imu500 (sdf b8f35590, airframe c747c8ff), IMU 500, 지도/노이즈/EKF/프로필 동일. **운영 플래그**: STOP_CAP_FIRST 1, STOP_ITEMS_RAMP 1, END_EXTEND 1, STALL_DETECT 1, 다른 후보 0, **서버 UGV_TEST_HOOKS=0** (run_sc_v10_ops = run_sc_v9 사본에서 서버 기동 TEST_HOOKS 1→0 한 줄; 실행 중 v9 는 건드리지 않음), **PARK_AFTER 요청 없음 → 실제 park 1.0 s**. ADAIR_RUN_ID 와 park_events.jsonl·로거 전율 topics 는 운영 동작을 바꾸지 않는 계측으로 유지 (park 표본 배열은 훅 0 이라 미수집 — 물리 자료 누락 아님).

## 회차
1. **o5_on_s3113_downabort_1** — 경사 중단 (s3113, 6 회 중 감독 여유 최소 사례). 외부 장면·중단 트리거 = f7 와 같음, END_EXTEND 1. 판정 final_judge_ops.py = final_judge_v7_1 + **0i_ops_env** (health.env 운영 플래그·TEST_HOOKS "0"·PARK_AFTER 없음·RUN_ID, driver park_policy after_s 1.0·test_hook false). 입력 요청 시점 gz 9.0~9.6, ⑤ ≤ min(needed+1, 35.3), 감독 ≥ 3 s, ③b/③c 물리 자체 정지·유지 (기존 1 s 증거 그대로), ③d park 정책 = 실제 after_s (1.0) 기준 [1.0, 1.6] — 기존 그대로, 30 s 유지, FAULT/CUT 없음.
2. **o5a_acc3_s1096_a** — 정상 도착 곡선 (E4f 와 같은 출발/목표). 판정 e4_judge_ops.py = e4_judge_v3 에서 1_evidence 의 park 기대를 after_s 1.0·test_hook false 로, 0i 기대를 운영 env 로만 변경. 목적지·연장·자체 정지 (7b/7c 1 s)·park 정책 (7d 실제 after_s 기준)·30 s 유지·STOP_PATH 없음·500 Hz 그대로.
- park 1.0 s 때문에 물리 자체 정지 증거가 부족하면 UNCONFIRMED 로 보존 (임계값 낮추지 않음).

## 순서·중단
1 → PASS 면 2. 비PASS·래퍼 rc≠0 즉시 중단·보고. 2/2 PASS 면 S5 운영 조합 확인 → 실제 지형 짧은 선별 (사전 실행표 고정 뒤).

## 판정기 확인 (물리 없음)
훅 1 자료에 운영 판정기 적용: f7 6 회 전부 0i_ops_env False → FAIL, e4f 3 회 1_evidence·0i False → FAIL (설정 불일치 검출).
