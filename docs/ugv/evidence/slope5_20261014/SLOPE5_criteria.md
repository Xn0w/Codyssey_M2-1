# 경사 정지 재시험 v5 — F1 + F2 + 정지 경로 항목화 (STOP_ITEMS_RAMP) 사전 기준 (2026-10-14 03:30:26, 실행 전)

근거: Fable 2026-10-14 원인 검토 (docs/ugv/UGV_경사정지_F1저속순항_페이블원인검토_20261014.md) ③⑤, Codex 0300 2·4·5절.
고정: 서버 ADAIR_wt_hook `341df20` (wip/stop-ramp = dc207ac + STOP_ITEMS_RAMP 후보·시간 원점 계측), 판정기 slope5_judge.py 76b2324d862f…, ULog 덤프 264dedfba737…, run_sc_v8, 선행 게이트 전체 단위시험 suite_stopramp 통과.
판정기 검증: s4r 지난 ON 8회에 적용 → 8/8 FAIL (0c 저속 상한 8/8, s3113 0a FAULT·CUT 3/3) — validate/judge_v5_on_s4r.json.

## 구성
ON = `UGV_STOP_CAP_FIRST=1 UGV_STOP_ITEMS_RAMP=1 UGV_PX4_PARK_AFTER_S=2.0`, END_EXTEND 0, 다른 후보 0, 차량 susp_a_acc3 (F2). 사례·도구 인자 = SLOPE4 (s0547 / s3113 하강 중단, --track-s 200 --post-stop-s 50).
OFF 기준 재사용: s4r_off_s0547 54.7 m·s4r_off_s3113 45.2 m (899bb56 — 341df20 은 플래그 off 에서 기록 필드만 추가, 정지 동작 같음) → 기준 48.9 / 40.6 m (SLOPE4 규칙).

## 순서 (Codex 0300 5절)
s3113 a → s0547 a → s3113 b → s0547 b → s3113 c → s0547 c. **매 회차 판정, PASS 아니면 즉시 중단** (FAIL/UNCONFIRMED/INVALID). 사례별 3 유효 PASS = 6/6 이면 'F1+F2+항목화 기본 on 후보' (S4 종료·운영 채택 아님).

## 회차 판정 (모두 참 = PASS, 확정 거짓 하나 = FAIL, 그 밖 자료 부족 = UNCONFIRMED)
0 공통 안전 선행: a FAULT/STOP_NOT_CONFIRMED/STOP_CUT_DRIVE/STOP_SLOW_FINISH_CUT 없음, b start_item = 0, c 상한 ≥ 정지 시작 속도 − 2.0 (저속 순항 상한 의존 없음), d STOP_CONFIRMED time_s ≤ t_allow − 3.0 (STOP_SUP_BEGIN) 그리고 travel ≤ allow.
① F1 상한 ACK·정지 미션 첫 트리플릿 = 상한 ±0.05. ② 명령 뒤 최고 ≤ 명령 시 + 0.5, 감속 시작 ≤ 1.0 s (STOP_PATH 시각 기준 — 진입·업로드 시각은 timing 으로 함께 기록).
③a speed setpoint 0 ≤ fin + 0.1, ③b/③c Gazebo 물리 정지·1 s 유지 disarm 전, ③d park NORMAL_STILL·still→disarm 요청 2.0~2.6 s·run_id = tag, ③e RUNAWAY_CAP·구동 차단 없음.
④ 차체 도로 안, 정지 뒤 30 s 이동 ≤ 0.1 m, yaw ≤ 5°. ⑤ 정지거리 < OFF 기준 그리고 ≤ needed + 1.0 (needed − 4 미만이면 미확인).
기록만: 보낸 항목 속도 열·STOP_PATH.timing·감독 매개변수·끝 진입 속도·Gazebo 정지→disarm.

## 보정 1 (04:02:14, s5_on_s3113_downabort_a 결과 뒤 — 판정 기준·판정기 불변)
- 선행 단위시험: suite_stopramp 접근 위반 rc 139 (GC 중 fire.py:34 densify ← test_stage3_drive, 오토 모드, 묶음 누적 1) → 새 ID suite_stopramp2 297 passed.
- s5_on_s3113_downabort_a = UNCONFIRMED: 0b start_item 자료 없음 — 드라이버가 시작 항목 0 이면 키를 남기지 않던 **기록 결함**. 다른 항목 모두 참 (상한 8.69, 정지 32.3 m, 정지 확인 8.5 s / 마감 12.24 s, FAULT·CUT 없음, NORMAL_STILL, 30 s 0 m). 기록 보존, 소급 PASS 아님.
- 조치: 판정기 해석을 바꾸지 않고 드라이버 기록을 고침 `ADAIR_wt_hook b9fe46b` (= 341df20 + follow() 가 start_item 0 도 기록, 1 줄·동작 불변, 관련 시험 63 passed). 첫 회차를 새 ID s5_on_s3113_downabort_a2 로, 이후 순서·중단 규칙 그대로.
