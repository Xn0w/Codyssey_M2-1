# 진단 9 — IMU 500 Hz 후보 s0547 경사 대표 1회 (Codex 0625 4절·Fable 표본화 검토 7절) — 사전 고정 (2026-10-14 06:27:58, 실행 전)

**후보 검증의 첫 대표 회차 (최종 500 Hz 조합의 반복 수에 포함 가능 — 사전 범위 안일 때만).** 회차마다 판정, 비PASS/무효면 즉시 중단·분석.

## 고정
- 변형 susp_a_acc3_imu500 (ADAIR_wt_vehicle 48f3e5f, model sha1 b8f35590, susp_a_acc3 대비 imu update_rate 한 줄), airframe = susp_a_acc3 (RA_ACC_RAD_MAX 3), IMU_INTEG_RATE 250, 물리 2 ms, 센서 노이즈·EKF 불변. 서버 ADAIR_wt_hook 03d5b5d, 플래그 = v5 ON (STOP_CAP_FIRST 1, STOP_ITEMS_RAMP 1, PARK_AFTER_S 2.0, END_EXTEND 0, 다른 후보 0, STALL_DETECT 1, LAT_ACCEL 1.0). s0547 하강 중단 (wj495731_0574_0583, B-ugv1, RP:683400547:165.9, --abort-after 2 --abort-on-downhill 0.03 --track-s 200 --post-stop-s 50). 전율 logger_topics.txt (회차 동안만) + gz 기록기. run_sc_v9. 태그 d9_slope500_s0547_a.
- 동등성 (사후 확장 금지): 중단 속도 9.1~9.5 m/s, needed 33.5~35.5 m, 정지 항목 3. 밖이면 '범위 밖 유효 탐색' — 반복 수 제외.

## 판정 1 — 적용 (실패 = 적용 미확인, 후속 중단)
gz IMU stamp 간격 2 ms; vehicle_imu_status.accel_rate_hz 500; vehicle_imu delta_velocity_dt 4000 µs (2 표본). 로거 sensor_accel 은 적용 확인 수단이 아님 (로거 3.5 ms 간격 — Fable 검토 (A)).

## 판정 2 — 제품/안전 (v5 판정기 slope5_judge.py, 기준 SLOPE5_criteria 와 같음: 0a~0d, ①~⑤, ③a~e)
FAULT/NOT_CONFIRMED/CUT/SLOW_FINISH 없음, start_item 0, 상한 ≥ 시작 속도 − 2.0, 정지 확인 ≤ t_allow − 3 s, F1 적용, 감속 시작 ≤ 1 s, ③a~e (park NORMAL_STILL·2.0~2.6 s·run_id), 도로 안·30 s ≤ 0.1 m·yaw ≤ 5°, 정지거리 < OFF 48.9 m 그리고 ≤ needed + 1.0. **진단 지표가 좋아도 이 판정 실패를 합격으로 바꾸지 않는다.**

## 판정 3 — 표본화 가설·EKF (Fable 7절 그대로, 기록·진단)
(1) E500 (gz 전 표본, gz pose 자세, W1) |·| ≤ 0.15; (2) 가상 250 짝/홀 기록, |차| ≥ 0.3 이면 '250 이었다면 편향' 표시 (작으면 반증 아님); (3) PX4 combined 동일 기준 E 와 E500 차 ≤ 0.01 (같은 경계·자세·truth·dt — stage_compare.py); (4) 관절 충격 10 ms·2 ms 지연·×21 재현 (cmd_vs_joint.py); (5) 제동 창 GNSS 혁신 평균 |·| ≤ 0.15, 지평 상태 − truth ≤ 0.1, Δpitch 변화 ≤ 0.4°; (6) 정지 뒤 EKF 부호 속도 최소 ≥ −0.35·최대 ≤ +0.10·재상승 없음; (7) park 초기화 0; (8) 정지 직전 출력 오프셋 −0.30~−0.15.
