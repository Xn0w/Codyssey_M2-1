# 경사 정지 반복 (F1 STOP_CAP_FIRST + F2 RA_ACC_RAD_MAX 3) — 사전 기준 (2026-10-14 01:55:44 작성, 실행 전)

근거: Fable 미해결 3.1~3.3, Codex 0130 순서 4·P2/P4 규칙, E4 v2 4/4 (F2+연장 채택 후보).
고정 버전: 서버 ADAIR_wt_hook `899bb56` (F1 0a8a35a 포함 확인 — merge-base = 0a8a35a), 판정기 `slope4_judge.py` 6fae1c8b1801…, ULog 덤프 `slope_ulog_dump.py` 264dedfba737…, 래퍼 run_sc_v7.
판정기 검증: E2 회차(e2acc_s0547_downabort_a)에 적용 → ① 2.48=2.48 ✔, ② ✔, ③a ✔, ③b ✔, ③c ✗ (0.985 s, 기존 E2 와 같음), 정지 유지는 관측 18.5 s 라 미확인 → 새 회차는 --post-stop-s 50.

## 구성
- ON: `UGV_STOP_CAP_FIRST=1 UGV_PX4_PARK_AFTER_S=2.0`, 다른 후보 0 (END_EXTEND 0 — 중단 정지 경로에는 적용 안 되는 기능이지만 비교 밖이라 끔), 차량 susp_a_acc3.
- OFF (s3113 새 기준 1회): 후보 전부 0, 차량 susp_a, 같은 서버.
- 사례: s0547 5.5 % 하강 중단 (B-ugv1, wj495731_0574_0583, RP:683400547:165.9), s3113 3~4 % 하강 중단 (A-ugv1, wj494846_1237_1921, RP:682503113:143.0). road_test --abort-after 2 --abort-on-downhill 0.03 --track-s 120 --post-stop-s 50. STALL_DETECT 1, LAT_ACCEL 1.0.
- 순서: s4r_off_s3113_downabort_a → s4r_on_s0547_downabort_a → (판정 PASS 일 때만) s4r_on_s0547_downabort_b, c, s4r_on_s3113_downabort_a, b, c. 접근 위반·래퍼 무효 누적 2회면 중단 (사용자 지시).

## ON 회차 판정 (Fable 3.3, 상태 INVALID/UNCONFIRMED/PASS/FAIL — E4 v2 규칙)
① STOP_PATH speed_cap_first.ok 참 이고 정지 미션 첫 트리플릿 cruise = 상한 ±0.05.
② 명령(STOP_PATH wall ↔ CSV wall_t, 맞춤 오차 ≤ 0.2 s) 뒤 Gazebo 최고 ≤ 명령 시 + 0.5 m/s, 감속 시작 ≤ 1.0 s (slope_report phase_split).
③a 정지 미션 finished 뒤 speed setpoint 0 ≤ fin + 0.1 (규칙 E4 v2). ③b/③c Gazebo (공백 ≤ 0.3 s). ③d 서버 park NORMAL_STILL·still→disarm 요청 ∈ [2.0, 2.6]. ③e RUNAWAY_CAP 아님·STOP_CUT_DRIVE 없음.
④ judge3 차체 도로 안, 정지 확인(명령 뒤 < 0.2 m/s 1 s) 뒤 30 s 수평 이동 ≤ 0.1 m, yaw 변화 ≤ 5°.
⑤ Gazebo 정지거리 < 같은 사례 OFF 최소 (s0547 48.9 m = chain_slope3 OFF 3회; s3113 = 새 OFF 회차 값, 그 값이 기존 40.6~43.2 m ±5 m 밖이면 OFF 2회 추가 뒤 판정) 그리고 ≤ 계획 정지 경로 needed_m + 1.0 m.

## 채택 규칙 (Fable 3.3 그대로)
F1 기본 on 후보 = ON 6회 ①②④⑤ 6/6. F2 채택 = 추가로 ③a~e 6/6 그리고 E4 통과(완료). 한 회차라도 실패 → 추가 회차 없이 원인 분석 (평균·다수결 없음). 통과해도 S4 종료·5~6 % 하강 운영 가능 선언 아님.
(태그 수정: slope_report 가 'abort' 포함 태그만 중단 회차로 분석 — 실행 전)

## 보정 (02:00:10, ON 회차 실행 전 — Codex 0155 반영)
- 체인 첫 판(chain_slope4.sh)은 합본 전체 단위시험 없이 시작돼 OFF s3113 1회 뒤 중단 (01:58). 그 OFF 회차(run_sc_v7, run_id 없음)는 OFF 기록 용도로만 쓴다: 45.2 m.
- 899bb56 이 F1(0a8a35a)을 이미 포함 (merge-base 확인) → 새 합본 = 899bb56 그대로. 전체 단위시험 suite_899bb56 통과가 ON 회차의 선행 게이트.
- _safe_stop 에 끝 지점 연장 없음: END_EXTEND 는 vehicle._drive 에서만 (_end_extend 호출 위치 1곳), 그리고 ON 도 END_EXTEND=0.
- ⑤ OFF 기준: 두 사례 모두 현재 합본 OFF 를 새로 1회 (s0547 은 9c49f69 OFF 3회 재사용 불가 — S6 경로·정지 관련 코드 차이). 새 값이 참고 범위 ±5 m 안이면 기준 = min(참고, 새), 밖이면 OFF 2회 추가 전 ⑤ 미확인. s3113 새 OFF 45.2 m → 기준 40.6 m.
- 래퍼 run_sc_v8 (Windows 서버에도 ADAIR_RUN_ID), ③d 는 park 기록 run_id = tag 일 때만 판정 (아니면 미확인).
- 순서: s4r_off_s0547_downabort_a → s4r_on_s0547_downabort_a (판정 PASS 일 때만) → 나머지 ON 5회.

## 보정 2 (02:19:20, s4r_on_s0547_downabort_a 결과 뒤 — 판정 기준 불변, 기록 창만)
- s4r_on_s0547_downabort_a = UNCONFIRMED: ④ 정지 유지 관측 22 s (< 30 s). 원인: road_test --track-s 120 (전체 기록 상한)이 --post-stop-s 50 보다 먼저 끝남 — 오퍼스 설정 결함. 다른 항목은 모두 참이었다 (기록 보존, 소급 PASS 아님).
- 조치: 판정 기준·판정기·서버·플래그 그대로, road_test --track-s 200 으로 기록 창만 늘려 첫 ON 회차를 새 ID s4r_on_s0547_downabort_a2 로 1회. 그 판정이 PASS 일 때만 나머지 5회 (같은 --track-s 200).

## 보정 3 (02:26:18, a2 결과 뒤 — 판정 기준 불변)
- s4r_on_s0547_downabort_a2 도 UNCONFIRMED (④ 관측 부족). --track-s 는 원인이 아니었다: road_test 중단 분기는 --post-stop-s 를 쓰지 않고 정지 뒤 고정 10 s 만 관측. 두 회차 모두 ④ 외 항목 전부 참 (a: 33.0 m, a2: 32.2 m, F1 2.69/2.13 일치, NORMAL_STILL). 기록 보존, 소급 PASS 아님.
- 조치: 시험 도구만 수정 `ADAIR_wt_hook dc207ac` (= 899bb56 + road_test 중단 분기 max(10, --post-stop-s) 관측, 서버 코드 변경 없음 — git diff 899bb56..dc207ac = ugv/tools/road_test.py 1곳, test_retest_tools 16 passed). 전체 단위시험 suite_899bb56 은 서버 코드 기준으로 유효.
- 첫 ON 회차를 새 ID s4r_on_s0547_downabort_a3 로 1회 → PASS 일 때만 나머지 5회.
