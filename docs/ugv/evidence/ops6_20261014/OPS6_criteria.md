# 운영 정차 2.0 s 후보 확인 — 통합 실행 계획·사전 기준 (2026-10-14, 실행 전, 리더 결정)

## 결정 반영
- 기존 1 s 기준 유지. o5_on_s3113_downabort_1 (0.962 s) 원본 FAIL·검토 UNCONFIRMED 유지 — 소급 합격 없음.
- 후보 = **운영 설정 UGV_PX4_PARK_STILL_S=2.0** (시험 훅 아님): 서버 ADAIR_wt_hook `wip/park-ops` **5dc1af4** = 03d5b5d + park_still_ops_policy (미설정 시 1.0 그대로, [1.0, 3.0] 자름, PX4 끝 지점 자체 정지 차만, 시험 훅이 먼저, RUNAWAY 4 s 상한 불변) + 시험 6 개 (test_park_hook·test_px4_plan 34 passed). 기본값·정식 모델 변경 없음.
- 상류 보고는 사용자 지시로 다음 주로 연기 (자료 준비 안 함). Fable Y 경계 검토는 그대로 진행 중 — 이 시험과 같은 회차에 지형 후보를 섞지 않음 (기존 tiles_v2 월드만 사용).

## 고정
- **정차 대기 외 변경 없음**: 체인이 `git diff --name-only 03d5b5d HEAD` = {ugv/drivers/px4.py, ugv/tests/test_park_hook.py} 확인 (아니면 HOLD), 서버 HEAD 5dc1af4, 차량 48f3e5f susp_a_acc3_imu500, 운영 조합 (CAP_FIRST 1·ITEMS_RAMP 1·END_EXTEND 1·STALL_DETECT 1·다른 후보 0, TEST_HOOKS 0 = run_sc_v10_ops, PARK_AFTER 요청 없음) + PARK_STILL_S=2.0, 장면 = ops5 와 같음. 동결 OPS6_freeze.sha1.
- 판정기: final_judge_ops2.py (= ops5 판정 + 0i 기대 env PARK_STILL_S "2.0"·park_policy after_s 2.0·test_hook false·basis '운영 설정'), e4_judge_ops2.py (1_evidence park 2.0·0i env). 확인: ops5 회차 (park 1.0) 에 ops2 판정기 → 0i False → FAIL.
- **공통 시간축 자체 정지** selfstop_gt_check2.py (ULog 한 시계: groundtruth 55 Hz 속도·위치, disarm 요청·armed 해제): 차단 전 연속 < 0.2 m/s 하한 ≥ 1.0 s (pass_1s), **대기 중 이동** = 저속 시작 ~ 차단 groundtruth 수평 변위 ≤ 0.05 m, 차단 뒤 30 s 변위 ≤ 0.05 m. 확인: o5 회차에 적용 → 0.962 s·pass_1s false (음성 검출).

## 회차·PASS (각 회차 = 판정기 PASS AND selfstop SS_OK, 래퍼 rc 0)
1. **o6_on_s3113_downabort_1** (원래 증거 부족 사례): 입력 요청 시점 gz 9.0~9.6, ⑤ 정지 ≤ min(needed+1, 35.3), 감독 여유 ≥ 3 s, ③b/③c (자체 정지·1 s 유지), ③d park 정책 [2.0, 2.6] (실제 after_s 기준), ③e NORMAL_STILL·RUNAWAY/CUT 없음, 0a FAULT/CUT 없음, 30 s 유지, 도로 경계, 0e·0f·0g·0i.
2. PASS 면 **o6a_acc3_s1096_a** (정상 도착 회귀): 목적지 ≤ 1 m·연장·7b~7e (자체 정지·park 2.0 정책)·30 s 유지·STOP_PATH 없음·500 Hz·0i.
비PASS·selfstop 실패·래퍼 rc≠0 이면 즉시 멈춤·보고. 같은 조건 자동 반복 없음.

## 기존 근거 재사용 범위 (같은 최종 설정 기준)
- 재사용 가능 (보조 근거): 훅 2.0 s 회차 — 경사 f7 6 회·도착 e4f 3 회 (정차 대기 시간이 같은 2.0 s, 차이는 TEST_HOOKS=1 의 park 표본 버퍼·시험 endpoint 존재뿐, 판단 로직 동일 — 소스 park_decide 공유). 운영 1.0 s 도착 o5a PASS 는 대기만 다름.
- 추가 검증 필요 (이번 2 회): 시험 훅 0 상태에서 운영 설정 경로 (park_still_ops_policy) 의 실제 적용·health.env·park_policy 증거, 경사 중단 1 s 자체 정지 (기존 미충족 항목), 도착 회귀.
- 범위 밖: 실제 지형 월드·Y 경계 (Fable 검토 중), 다른 차종, 장거리.
## 다음
두 회차 PASS → S5 운영 조합 (PARK_STILL_S=2.0 포함) 고정 여부 판단 보고 (기본값 변경은 별도 결정).
