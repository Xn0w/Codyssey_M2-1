# E4f — 최종 500 Hz 후보 정상 도착 회귀 사전 기준 (2026-10-14 07:2x, 실행 전, Codex 0650 3절·0723)

## 목적·범위
이미 합의한 **기존 E4 의 acc3 ON 곡선 2회 (s1096 a·b)·직선 1회 (s3113 a)** 를 최종 500 Hz 후보로 재실행. 새 목표·새 안전 기준 없음. RA −1 (raoff) 분기는 분기 코드/파라미터 불변이라 기존 근거(e4b_raoff_s1096_a PASS) 재사용 — 재실행 안 함. 전체 Python 시험·교차로 매트릭스 재실행 안 함.

## 동결
서버 ADAIR_wt_hook `03d5b5d` (e4b 의 899bb56 + b9fe46b start_item 기록·03d5b5d park 표본 버퍼 (훅 전용)·341df20 STOP_ITEMS_RAMP (플래그)·dc207ac 중단 대기 — 정상 도착 경로 변경 없음), 차량 `48f3e5f` susp_a_acc3_imu500 (model sha1 b8f35590, RA_ACC_RAD_MAX 3), IMU 500 Hz, 물리 2 ms, 노이즈·EKF·GNSS 지연·park 문턱·감독 불변, tiles_v2. 래퍼 run_sc_v9 (gz 기록기 없음, ADAIR_RUN_ID 있음), 전율 logger_topics 설치(회차 동안만).
플래그 = 경사 최종 후보와 같은 조합 + E4 설정: STOP_CAP_FIRST 1, STOP_ITEMS_RAMP 1 (둘 다 중단 정지 경로에서만 동작 — 0h 로 정상 도착 회차에 STOP_PATH 없음을 확인), **END_EXTEND 1 (E4 전용 설정, 끝 지점 3 m 연장)**, PARK_AFTER_S 2.0, 다른 후보 0, STALL_DETECT 1, LAT_ACCEL 1.0. 장면 (월드·출발·목표·track-s 170·post-stop-s 35) = e4b 와 같음.

## 회차 판정 — e4_judge_v3.py = E4 v2 기준 (E4_criteria_v2.md 1~8, 7b~7e) 그대로 +
- 0e 500 Hz 적용 (vehicle_imu_status accel_rate ≈ 500, delta_velocity_dt 4000), 없으면 UNCONFIRMED.
- 0h 정상 도착 회차에 STOP_PATH 이벤트 없음.
- 상태 우선순위: INVALID > FAIL > UNCONFIRMED > PASS (v2 는 UNCONFIRMED 가 FAIL 보다 앞 — v3 에서 FAIL 우선으로).
판정기 확인 (물리 없음): 250 Hz e4b/e4 묶음 재판정 → 전부 UNCONFIRMED (0e 없음, PASS 0). 목적지 기준을 인위로 0.2 m 로 좁히면 0.349/0.422 m 회차 FAIL (0e 누락보다 FAIL 우선) 확인.

## 순서·중단
경사 v7.1 체인이 `s3113 3/· s0547 3/` 으로 끝났을 때만 자동 시작 (아니면 HOLD). s1096 a → s1096 b → s3113 a 직렬, **비PASS·래퍼 rc≠0 즉시 중단·보고**. 3/3 PASS 뒤 S5 후보 고정 판단은 별개 (Codex 보고 후).

## 07:3x 보강 (Codex 0728, 첫 회차 전)
- 판정기 v3 에 **0i 서버 실제 환경** 추가: road_test health.env 의 UGV_STOP_CAP_FIRST 1·UGV_STOP_ITEMS_RAMP 1·UGV_PX4_END_EXTEND 1·UGV_PX4_PARK_AFTER_S 2.0·UGV_MODEL_VARIANT susp_a_acc3_imu500·UGV_TEST_HOOKS 1·ADAIR_RUN_ID=태그. 기록 없으면 미확인. 확인: e4b 묶음 (CAP_FIRST 0, susp_a_acc3) 은 0i False → FAIL (구성 불일치 검출). END_EXTENSION 실제 적용은 기존 1_evidence (offset 3.0), park 은 7d/7e, 500 Hz 는 0e.
- **진입 전 읽기 전용 확인 e4f_precheck.py**: 현재 final7/f7_judge.json 에서 사례별 고유 태그 PASS 3·총 6, 비PASS 없음, 회차별 rc/표식, 회차 로그 FINAL7R_RESULT PASS (s3113_1 은 v7 FAIL + ORIGINAL 보존 = 정정 이력), FINAL7R_freeze.sha1 해시 일치. 불일치면 E4f 만 HOLD. (07:3x 실행 시 'PRECHECK_HOLD s3113 PASS 2≠3 | s0547 PASS 1≠3' — 경사 진행 중이라 정상, 해시 불일치 없음.)
- 대기 체인 재시작: 07:26 의 첫 대기 체인 (아직 대기 루프, 회차 미실행) 을 종료하고 보강본으로 다시 시작. 경사 체인·공유 래퍼는 건드리지 않음.
