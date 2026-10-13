# 진단 7 — IMU 입력 경로 평지 1 + 경사 1 (Codex 0540) — 사전 고정 (2026-10-14 05:38:34, 실행 전)

**입력 경로 진단이며 제품/정지 안전 채택 검증이 아니다.** 반복·주파수/물리 스윕 없음. 평지를 먼저 읽고 기록 목적이 충족됐을 때만 경사.

## 고정 (제어 조건 동등)
- 서버 ADAIR_wt_hook `03d5b5d` (진단 A 와 같음), 플래그 = 진단 A (STOP_CAP_FIRST 1, STOP_ITEMS_RAMP 1, PARK_AFTER_S 2.0, END_EXTEND 0, 다른 후보 0, STALL_DETECT 1, LAT_ACCEL 1.0), 차량 susp_a_acc3 (B-ugv1, 인스턴스 3, adair_ugv_3), 같은 s0547 도로 좌표·목표 RP:683400547:165.9·같은 road_test 인자 (--abort-after 2 --abort-on-downhill 0.03 --track-s 200 --post-stop-s 50; 중단 위치 판정은 타일 지형 자료로 하므로 평지에서도 같은 지점).
- 평지 = kangwon_flat (평면 z 0, 같은 x·y), 스폰 z 0.45 (지면 + 0.45 관례). 경사 = wj495731_0574_0583.
- **바꾸는 것은 기록 설정만**: PX4 빌드 etc/logging/logger_topics.txt (diag7/logger_topics.txt — sensor_accel·sensor_gyro·vehicle_imu(_status)·sensor_combined·actuator_*·rover_*·위치/자세 groundtruth·estimator 일부 전율) 를 회차 동안만 두고 끝나면 삭제 (빌드 etc 공유 — 그동안 다른 PX4 기동 없음). SDLOG_PROFILE 등 파라미터 불변 — 회차 ULog 초기 파라미터를 진단 A 와 diff 해 확인. gz 기록기 diag7/gz_rec.py (IMU 원 sim stamp·수신 wall, pose/info 의 모델 자세, 바퀴 joint_state, command/motor_speed) — 회차 동안 WSL 별도 프로세스.
- 실행 스크립트 run_flat_v9.sh / run_sc_v9.sh (= v8 + GZ_REC_MODEL 기록기 훅, 평지판은 run_flat_ab 와 같은 평지 변경).
- 난수 시드 고정 수단 없음 — 한계.

## 정의·판정 (결과 전)
- E = 세계좌표 진행 방향 IMU Δv − 같은 기준점·시간 truth Δv, 창 W1 = [fin−2.5, fin−0.05] (imu_cause.py 고정 창, sha1 기록). **과대 감속 = E < 0.**
- 평지: |E| ≤ 0.15 m/s → 평지 정상. 경사: E ≤ −0.60 m/s → 과대 재현. 근거: 정적 창 잔차 ≤ 0.006, 등속·강제동 0.03 (Fable 18 회차) → 0.15; 경사 과대 회차 −0.77~−1.33, 무과대 s0547 a +0.37 → −0.60.
- 해석: 평지 정상 ∧ 경사 큰 음수 = **이번 한 쌍에서 경사 연관 지지** (원인·필요/충분조건 확정 아님; s0547 a 반례). 둘 다 음수 = 경사 필수 설명 약화. 둘 다 작거나 미재현 = 미결 — 재실행으로 맞추지 않음.
- 단계 비교: sensor_accel 원시×dt / vehicle_imu delta_velocity / combined 합의 ±0.01 m/s (같은 구간·좌표·보정 단계·실제 dt 일 때만; 아니면 차이 설명). gz IMU 적분 vs gz pose 차분 (같은 sim stamp 구간) 과 PX4 입력의 일치/불일치로 gz 센서/물리 vs 브리지 분기. 주기: 실제 토픽 주기 측정, 부족하면 보간 안 하고 '물리 대 표본화' 미확인.
- 기록 유효성 (평지 뒤 확인, 미충족이면 경사 자동 실행 안 함·도구 수정·새 ID): sensor_accel·vehicle_imu ≥ 200 Hz 표본 (누락 < 1 %), integral dt 연속, actuator_motors 실제 주기, gz imu.csv ≥ 200 Hz·stamp 단조, pose·joint·cmd 수신 > 0, 모델 이름 일치.
- 제품 판정(v5 판정기)은 따로 기록만. 예기치 않은 물리 이탈·FAULT/CUT·기록 오염이면 후속 주행 없음.

## 보정 1 (05:44:09, 평지 a 뒤 — 기준 불변, 도구만)
- d7_flat_s0547_a: 중단 같은 지점 (앞 44 m −5.5 % 타일 자료, 9.3 m/s), rc 0, PX4 전율 기록 유효 (sensor_accel·vehicle_imu·combined 250 Hz, actuator_motors 100 Hz, groundtruth 55.6 Hz), **gz 기록 없음** — 기록기 훅이 `bash -lc` + 맨 & 라 wsl.exe 세션 종료와 함께 사라짐 (수동 재현 확인). 기록 불완전으로 보존 (PX4 쪽 자료는 참고 분석 가능).
- 조치: run_flat_v9·run_sc_v9 훅을 서브셸·setsid·stdin /dev/null 로, 기동 여부 GZREC_STARTED/NOT_RUNNING 을 start_<TAG>.txt 에 남김. 평지를 새 ID d7_flat_s0547_b 로.

## 평지 b 판독 (05:51:18, 경사 전) — 기록 유효 → 경사 진행
- 기록: PX4 sensor_accel·vehicle_imu·combined 250 Hz (누락 0, dt 4 ms), actuator_motors 100 Hz, gz IMU 250 Hz 단조, pose 55.6 Hz (18 ms), joint 500 Hz, cmd ≈ 20 Hz wall (Actuators header stamp 0 — 미기록, wall 만), 모델 이름 일치, GZREC_STARTED.
- 브리지: gz IMU ↔ PX4 sensor_accel 오프셋 0 (hrt = sim stamp), 겹침 표본 100 % 가 |차| ≤ 5.4e-6 (x 같음, y·z 부호 반대).
- E (W1): PX4 imu_cause −1.146, gz IMU × gz 모델 자세 −1.157, × PX4 groundtruth −1.157 (두 자세 출처 일치, 피치 ≈ 0°). gz IMU orientation 필드는 방위 규약이 달라 순항에서도 +3.5 → 사용 안 함. 정지 −0.002, 순항 −0.048.
- 사전 판정: 평지 |E| ≤ 0.15 아님 (E −1.15) → '경사 필수' 설명 약화. 참고: 기록 불완전 평지 a 는 E +0.45 (같은 평지에서 부호 반대).
