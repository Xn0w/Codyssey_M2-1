# imu_cause_20261014 — 재현 정보 (Fable 읽기 전용 검토, 2026-10-14)

## 설치본 (WSL Ubuntu-24.04, 사용자 geumsoni)
- PX4: `~/PX4-Autopilot` git describe `v1.18.0-beta1-446-g21fa379fb8` (ULog `ver_sw 21fa379fb87b60b644b035aa5d38f683819be4ad`, PX4_SITL).
  - IMU 경로 소스: `src/modules/simulation/gz_bridge/GZBridge.cpp` imuCallback (timestamp = hrt_absolute_time(), FLU→FRD 회전만, gz 메시지 stamp 미사용; `_px4_accel.update(timestamp, …)` → `PX4Accelerometer::update` timestamp_sample = 그 값), poseInfoCallback (groundtruth = 모델 pose_v 의 위치 차분 / dt, dt 는 수신 간격 [0.001, 0.1] s 로 제한, ENU→NED).
  - `src/modules/sensors/vehicle_imu/VehicleIMU.cpp` (가속도 적분기 reset 간격 = IMU_INTEG_RATE; delta_velocity = Σ accel·dt, 보정 `_accel_calibration.Correct`), `src/modules/sensors/voted_sensors_update.cpp:157-170` (sensor_combined.accelerometer_m_s2 = delta_velocity / delta_velocity_dt, integral_dt = delta_velocity_dt).
  - msg/VehicleImu.msg: delta_velocity = FRD 차체 좌표 m/s (적분 구간 delta_velocity_dt us), clipping 비트.
- Gazebo: `gz sim --version` 8.15.0 (gz-sim8-cli 8.15.0-1~noble), gz-physics7 7.8.0 (libgz-physics7-dartsim + libdart-core 6.13.2, libgz-physics7-bullet 도 설치). 월드 SDF 에 물리 플러그인 명시 없음 → gz-sim 기본(dartsim) [가설: 로그에 엔진 이름 없음, `default_physics` profile 만 기록]. `<physics type="ode">` 속성은 gz-sim 엔진 선택에 쓰이지 않는다.
- 월드: `ADAIR/logs/ugv/stage5/tiles_v2/wj495731_0574_0583.sdf` (s0547), `wj494846_1237_1921.sdf` (s3113): `max_step_size 0.002`, `real_time_update_rate 500`, gravity 9.8. E4: s1096 월드(타일). 평지 참고: `adair_flat.sdf` (같은 physics 블록).
- 차량: `ADAIR_wt_vehicle/ugv/gazebo/variants/susp_a_acc3` (MANIFEST: model_sdf_sha1 cf71aa0bb30aff2339bf7f6abf64edc887df11b5, susp k 130000 c 8000 ref −0.03 travel 0.1 link_mass 5, airframe RA_ACC_RAD_MAX 3). IMU 센서: base_link 원점(pose 미지정 = 링크 원점, 링크 원점은 모델 원점 +0.35 m), inertial CoM 링크 +0.1 m, update_rate 250, 노이즈 가속 0.00637/0.00637/0.00686, 자이로 0.00087. E1 = susp_a (RA −1), flat_base_stop30 = 기본 adair_ugv(서스펜션 없음, 2026-10-12).
- PX4 파라미터(ULog): IMU_INTEG_RATE 250, IMU_GYRO_RATEMAX 400, IMU_ACCEL_CUTOFF 30, EKF2_PREDICT_US 10000, EKF2_GPS_V_NOISE 0.3, GPS_P_NOISE 0.5, ACC_NOISE 0.35, ACC_B_NOISE 0.003, ABL_LIM 0.4, ABL_TAU 0.5, GYR_NOISE 0.015, IMU_POS 0/0/0, GPS_CTRL 7, IMU_CTRL 7, CAL_ACC0 XOFF 0 XSCALE 1, SDLOG_PROFILE 131, EKF 인스턴스 1, sensor_accel/vehicle_imu 인스턴스 0.

## 기록률 (d6_A ULog, imu_cause_d6_A_s0547.json rates)
sensor_combined 4.0 ms (250 Hz, 최대 간격 12 ms, 22184 표본, integral_dt 4000 us, clipping 0) · sensor_accel 1000 ms (로거 감쇄) · vehicle_imu 500 ms (로거 감쇄, dv_dt 4000 us) · vehicle_local_position_groundtruth 18 ms (p99 36) · vehicle_attitude_groundtruth 18 ms · vehicle_local_position 8 ms · estimator_states 8 ms (timestamp − sample 0.152 s = 융합 지평 지연) · estimator_aid_src_gnss_vel 32 ms (0.156) · vehicle_gps_position 32 ms (timestamp − sample 0.110 s). actuator_motors / rover_* 100 ms (로거 감쇄 — 실제 주기 로그에서 미확인).

## ULog (경로 `/home/geumsoni/.adair-ugv/<inst>/log/2026-10-13/…`, sha1 는 각 imu_cause_*.json)
d6_A_s0547 px4-3 20_00_44 (sha1 3d8df7dad863…) · v5 s0547 a/b/c px4-3 19_06_19 / 19_13_50 / 19_21_21 · v5 s3113 a2/b/c px4-1 19_02_32 / 19_10_04 / 19_17_35 · E4 acc3 s1096 a/b px4-3 16_06_43 / 16_10_45 · E4b acc3 s1096 a/b px4-3 16_35_58 / 16_40_01 · E4 acc3 s3113 a px4-1 16_18_22 · E4b acc3 s3113 a px4-1 16_47_47 · E2 px4-3 07_00_21 · E1 px4-3 06_34_15 · s4r OFF s0547 px4-3 17_12_30 · s4r OFF s3113 px4-1 16_56_15 · flat_base_stop30 px4-1 `2026-10-12/11_40_18`.

## 스크립트 (sha1)
- `imu_cause.py` 9eb573bf58479c5fc895ba4f8a8b412d3089caf4 · `imu_phase.py` 670679c3fa8516ec7cabd2319e89d0ad7cad8e98 · `prev_supplement/ekf_deep.py` ad410c3880763a6bb2995e098828f42fd65b7a40
- `imu_cause.py` — 단계별 적분·창·스펙트럼·EKF 지표 → `imu_cause_<label>.json`; `imu_cause_summary.csv` 집계.
- `imu_phase.py` — IMU 격자 위상·명령 시각 대조 → `imu_phase_out.txt`.
- `prev_supplement/ekf_deep.py`, `ekf_deep_*.json`, `ekf_quant.txt` — 앞선 보충 보고(EKF 표류)의 스크래치 산출물 보존.
계산 파라미터: 진행 방향 단위벡터 = fin−1.0 s truth 속도 (off 모드: t_mis+0.5), 중력 9.8 (NED +z), truth 가속 = truth 속도 ±0.1 s 중앙 차분, 창 정의는 imu_cause.py 머리말, 스펙트럼 = 창 안 detrended x 의 DFT(median dt 기준).
