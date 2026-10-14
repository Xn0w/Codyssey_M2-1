# 최종 500 Hz 경사 정지 검증 — 사전 기준 (2026-10-14 06:41:45, 실행 전, Codex 0650)

## 동결
서버 ADAIR_wt_hook `03d5b5d`, 차량 ADAIR_wt_vehicle `48f3e5f` 변형 susp_a_acc3_imu500 (model sha1 b8f35590; airframe RA_ACC_RAD_MAX 3), 물리 2 ms, IMU 500 Hz·IMU_INTEG_RATE 250, 노이즈·EKF·GNSS 지연 불변, 지도 tiles_v2. 플래그 = v5 ON (STOP_CAP_FIRST 1, STOP_ITEMS_RAMP 1, PARK_AFTER_S 2.0, END_EXTEND 0, 다른 후보 0, STALL_DETECT 1, LAT_ACCEL 1.0). 판정기 final500/final_judge.py (sha1 아래) = v5 판정 항목 + (final v6) 0e 500 Hz 적용·0f 분류 대조·입력 범위. 래퍼 run_sc_v9 (전율 logger_topics + gz 기록). GNSS 지연·EKF·park 문턱·감독 시간·제어 관절 변경 없음.

## 입력 범위 (STOP_PATH 이벤트, 소수 둘째 자리 — 경계 정밀도 한계)
- s0547: speed 9.2~9.6 m/s, needed 33.5~35.5 m, 항목 3. **사전 충돌 계산**: 기존 회차 9.55 → needed 35.4 — needed ≈ v²/(2·1.5) + 5 이라 9.6 이면 ≈ 35.7 > 35.5. 실질 상한 ≈ 9.58 (needed 상한이 지배), needed 범위 변경 없음.
- s3113 (자기 사례 기존 분포 9.18~9.33 / 33.1~34.0 / 항목 4): speed 9.1~9.4, needed 32.8~34.3, 항목 4.
- 범위 밖 = OUT_OF_RANGE (탐색 보존, 반복 수 제외). 범위는 다시 옮기지 않는다.

## 순서·중단
s3113 첫 → s0547 첫 → 교대로 각 사례 **유효 PASS 3회**까지. 회차마다 판정 — FAIL/UNCONFIRMED/INVALID 면 즉시 중단·보고. OUT_OF_RANGE 는 계속하되 반복 수 제외, 사례당 시도 최대 5회 (넘으면 중단·보고). 접근 위반·래퍼 무효 누적 2회면 중단 (사용자 지시). 태그 f5_on_<사례>_downabort_<n> (이름은 분류 증거가 아님 — 0f 로 STOP_PATH 증거와 대조).

## 회차 PASS = v5 판정 전 항목 + 0e (vehicle_imu_status accel_rate ≈ 500, delta_velocity_dt 4000) + 0f (태그 ON·중단 ↔ STOP_PATH F1 상한·항목화 존재) + 입력 범위 안.
첫 s3113·첫 s0547 은 상세 IMU/단계 비교(evidence_v2 --virtual250, EKF 부호 속도) 를 추가 기록 (판정 외).
