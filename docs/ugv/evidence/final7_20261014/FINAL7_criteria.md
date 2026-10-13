# 최종 500 Hz 경사 정지 검증 v7 — 사전 기준 (2026-10-14, 실행 전, Codex 0705)

## 목적
250 Hz 와 같은 내부 상태 비교가 아니라, **최종 500 Hz 후보가 지정된 두 장면(s3113, s0547 내리막 중단)에서 안전하게 정지하는지 보는 신규 확인 시험**. f5 다섯 회차(v6: 제품 PASS 5 / 입력 범위 밖 5 / 최종 인정 0)는 소급 편입하지 않음.

## 동결 (FINAL500 과 동일)
서버 ADAIR_wt_hook `03d5b5d`, 차량 ADAIR_wt_vehicle `48f3e5f` 변형 susp_a_acc3_imu500 (model sha1 b8f35590; RA_ACC_RAD_MAX 3), 물리 2 ms, IMU 500 Hz·IMU_INTEG_RATE 250, 노이즈·EKF·GNSS 지연·park 문턱·감독 시간 불변, 지도 tiles_v2. 플래그 v5 ON (STOP_CAP_FIRST 1, STOP_ITEMS_RAMP 1, PARK_AFTER_S 2.0, END_EXTEND 0, 다른 후보 0, STALL_DETECT 1, LAT_ACCEL 1.0). 사례 장면(월드·출발/자세·도로/목표·순항 속도·중단 트리거 --abort-after 2 --abort-on-downhill 0.03) 은 FINAL500 과 같음. 래퍼 run_sc_v9.

## 입력 조건 (변경점)
- **두 사례 공통: 중단 요청 시점 Gazebo 수평 속도 9.0~9.6 m/s** (양 끝 포함). 약 9.3 m/s 대표 조건의 제한된 변동 허용이며 구간 전체 안전 보증 아님. 기존 EKF(STOP_PATH) 기준 조건과 지표가 다름.
- 요청 시각 = road_test `abort.sim_t_cmd` (요청 순간 기록 CSV 마지막 sim_t — 요청 wall 시각과 같은 행). 속도 = 기존 gz_speed 0.2 s 위치 차분 창, 창 중심이 요청 시각에 가장 가까운 표본. 창 폭·선택 오차 기록. 요청 시각 없거나 대응 자료 없으면 UNCONFIRMED. EKF 로 대체하지 않음.
- STOP_PATH speed_mps·needed_m·항목 수는 **기록만** (유효성 판정 아님). 대신 0g: needed = round(v²/(2·1.5) + 5.0, 1) 일치 (±0.051).

## 회차 PASS
v5 판정 전 항목 (0a~0d, ①~⑤, ③a~e) + 0e (500 Hz 적용) + 0f (태그 ↔ STOP_PATH 분류) + 0g + 입력 조건 안, 그리고
- **⑤ 정지거리 ≤ min(이번 needed + 1 m, 사례별 절대 상한)** — s3113 35.3 m, s0547 36.5 m, 그리고 기존 OFF 최소보다 짧음.
- 감독 여유 ≥ 3 s, FAULT/CUT 없음, 자체 정지·정상 park·도로 경계·30 s 유지 그대로.
- 범위 밖 = OUT_OF_RANGE (반복 수 제외, 성공으로 숨기지 않음).

## 순서·중단
s3113 첫 → s0547 첫 → 교대로 각 **유효 PASS 3회** (첫 회차 포함). **어느 회차든 비PASS (FAIL/UNCONFIRMED/INVALID/OUT_OF_RANGE) 또는 래퍼 rc≠0 이면 즉시 중단·보고** — OUT_OF_RANGE 자동 반복 없음. 태그 f7_on_<사례>_downabort_<n>. 첫 s3113·첫 s0547 은 상세 IMU/단계 비교 (evidence_v2 --virtual250) 추가 기록.

## 판정기 확인 (물리 시험 없이, 실행 전)
judge_check_v7.py 로 과거 묶음 재판정: s5 FAIL/UNCONFIRMED 와 s4r ON FAIL 그대로, 범위를 인위로 9.0~9.1 로 좁히면 해당 회차 OUT_OF_RANGE, sim_t_cmd 제거 시 전부 UNCONFIRMED — 범위 이탈·자료 누락·제품 FAIL 이 PASS 로 바뀌지 않음. f5 의 v7 재판정 (요청 시점 gz 9.06~9.30, 전부 PASS) 은 **사후 참고 분석**일 뿐 반복 수에 넣지 않음.
