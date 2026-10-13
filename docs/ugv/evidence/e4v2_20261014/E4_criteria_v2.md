# E4 v2 — 새 4회 묶음 사전 기준 (Codex 0130 반영, 2026-10-14 01:35:06 작성, 새 회차 실행 전)

고정 버전: 서버 ADAIR_wt_hook `899bb568d301e93469c023bb84b7d19c7501398d` (wip/park-instrument = 17a7305 + park 실제 분기 계측), 판정기 `e4_judge_v2.py` sha1 c1c66fb9b7ea… (01:3x 수정: slope_report 출력을 e4b_ 별도 파일로 — v1 보존), ULog 덤프 `e4_ulog_dump_v2.py` 5c58f872684a…, 래퍼 `run_sc_v7.sh` f95c8d00d1c0…. 회귀: test_park_hook·test_px4_plan·test_stop_command_safety·test_end_extension 43 passed.
기존 E4 4회(e4_*)는 v1 기준 원본(2/4 FAIL)대로 보존한다. v2 판정기를 소급 적용하면 서버 기록이 없어 UNCONFIRMED 이며 소급 PASS 하지 않는다.

## 실행 순서
1. **E4-1 곡선 1회** `e4b_acc3_s1096_a` (susp_a_acc3, s1096_down) 먼저. 실제 park 분기·서버 타이밍·물리 정지·자료 유효성 확인.
2. 1회가 PASS 일 때만 같은 버전으로 `e4b_acc3_s1096_b`, `e4b_raoff_s1096_a`, `e4b_acc3_s3113_a` 직렬. FAIL/UNCONFIRMED/INVALID 면 나머지 자동 실행 안 함, 보고.
구성·플래그는 v1 과 같다 (END_EXTEND 1, PARK_AFTER_S 2.0, 다른 후보 0, STALL_DETECT 1, LAT_ACCEL 1.0).

## 회차 상태
- INVALID: rc 파일 없음, test/copy_logs/stop_post rc ≠ 0, invalid_stop, contaminated·invalid_evidence 표식.
- UNCONFIRMED: 필요한 자료 누락 (서버 park 기록·ULog·Gazebo 공백 > 0.3 s 등) — PASS 아님.
- PASS: 아래 모두 참. FAIL: 하나라도 거짓.

## 항목 (v1 1~6·8 그대로, 7 교체)
1 증거 게이트 · 2 서비스 목적지 ≤ 1.0 m (Gazebo 정지 위치) · 3 seq 끝 도달·단조 (경유점 누락 없음과 동등하지 않음 — 미확인으로 기록) · 4 judge3 + E3 ±0.3 m · 5 정지 뒤 30 s ≤ 0.1 m · 6 (acc3) ULog speed setpoint 0 을 [fin−0.5, fin+2] 첫 0·fin+0.1 까지 연속으로 찾아 ≤ fin + 0.1 · 8 ARRIVED to_dest ≤ 1.0.
7 (acc3 만; RA −1 은 기록):
- 7b 물리 정지 (Gazebo): [fin−2, fin+1.5] 에서 < 0.2 m/s 도달, finished 이전이면 그 시각~finished 내내 < 0.2, disarm(ULog) 전. 판정 구간 Gazebo 표본 최대 공백 ≤ 0.3 s 아니면 미확인.
- 7c 물리 정지 유지 (Gazebo): 7b 뒤 < 0.2 연속 ≥ 1.0 s 가 disarm 전에 끝남.
- 7d 서버 정책 (서버 monotonic, park_events.jsonl): 실제 선택 분기 = NORMAL_STILL, after_s = 2.0, disarm 요청 − still_since ∈ [2.0, 2.0 + 폴링 0.5 + 잠금 0.1]. 기록 없으면 미확인.
- 7e 실제 분기 ≠ RUNAWAY_CAP 이고 STOP_CUT_DRIVE 이벤트 없음. 기록 없으면 미확인.
- 기록만: Gazebo 정지→disarm (v1 의 7d), ULog EKF 속도 정착 지연, 정렬 오프셋·rms (rms 는 시각 불확실성 아님).

## 묶음 판정
4/4 PASS → F2+연장 한 짝 채택 후보 (운영 기본값 아님, Codex 검토). 하나라도 FAIL → 채택 안 함·원인 분석. 같은 실패 반복 → Fable. 분기 증거가 있는 실제 상한 사용/물리 실패는 시간 창만 바꿔 해결하지 않는다.
