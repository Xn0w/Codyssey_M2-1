# imu_sampling_review_20261014 — 재현 정보 (Fable 읽기 전용, 2026-10-14)

## 설치본 (앞선 `imu_cause_20261014/PROVENANCE.md` 와 같음)
PX4 `~/PX4-Autopilot` 21fa379fb8 (v1.18.0-beta1-446), gz-sim 8.15.0, gz-physics 7.8.0 (dartsim 6.13.2 기본 추정), 물리 2 ms/500 Hz, 차량 susp_a_acc3 (model_sdf_sha1 cf71aa0b…; 진단 8 변형 susp_a_acc3_imu500 = imu update_rate 500 한 줄, b8f35590), 서버 ADAIR_wt_hook 03d5b5d.
읽은 소스: `src/modules/logger/logger.cpp` (instantiate 262-292: 기본 `log_interval` 3500 µs, `-r` 로만 변경; `copy_if_updated` 455-473: interval 0 이면 `sub.update(buffer)` = 최신 메시지 1건 복사(큐 없음); 696 `hrt_call_every(_log_interval)` 고정 주기 루프; 540-542 FIFO 토픽일 때만 800 µs), `ROMFS/.../rc.logging:57` (`logger start -b … -t ${LOGGER_ARGS}`, `-r` 없음), `init.d-posix/rcS:172-174` (SDLOG_MODE 1, SDLOG_PROFILE 131), `src/modules/sensors/vehicle_imu/VehicleIMU.cpp` (586 `accel_rate_hz = 1e6/_accel_mean_interval_us.mean()`; 685-704 `accel_integral_samples = round(integration_interval/accel_interval)`, reset_interval (n−0.5)·interval), `GZBridge.cpp:435-447`.

## 자료
- gz 기록 (`logs/ugv/stage6/diag7/gzrec_*`, sha1 는 `sampling_*.json["sha1"]`): d7_flat_s0547_b (imu b3515b7c…, pose e6ff61fa…, joint b9de9ca3…, cmd a4fc6be9…), d7_slope_s0547_a (5197149…, be499259…, d9afbf38…, cb7ca58d…), d8_flat500_s0547_a (778f8239…, 35cee7fe…, cebc5d75…, c706beff…). 열: imu(stamp sim, ax ay az FLU, …), pose(stamp, x y z ENU, q), joint(stamp 2 ms, name, pos, vel), cmd(stamp=0, wall, v0).
- ULog (px4-3 2026-10-13): d7_flat_a 20_38_57, d7_flat_b 20_44_24 (cf4d0a18…), d7_slope_a 20_51_35 (caaa8976…), d8_flat500 21_05_01 (f23da714…) — sha1 는 `stage_compare_*.json`/diag7·8 evidence_v2.
- fin(sim) = 정지 미션 finished (evidence_v2): flat_b 89.292, slope_a 91.772, flat500 90.284. 창 W1 [fin−2.5, fin−0.05], cruise [fin−5, fin−3], static [fin+0.8, fin+2.5].

## 스크립트 (sha1) → 산출
- `sampling_test.py` a8bd6a154a491b8c1cb454b080d04f53f3f52db4 → `sampling_{d7_flat_b,d7_slope_a,d8_flat500}.json`: 관절 속도(네 바퀴 평균 × r 0.35) 스텝 가속도, IMU↔스텝 모델 적합, 짝/홀 반사실, 20 ms(10 스텝) 슬롯 평균, 충격 시각·간격·슬롯, cmd.csv wall 통계.
- `stage_compare.py` 5391ed37d716b5667eea2ce2716ff3b5572d8f07 → `stage_compare_{d8_flat500,d7_flat_b}.json`: 동일 경계·자세·truth·실제 dt 로 gz 500 Hz / PX4 combined / 로거 sensor_accel E 비교 ((B)).
- `cmd_vs_joint.py` 29a7ee3b7b16b8a430f9f06aebeff220541a8481 → `cmd_vs_joint_*.json`: PX4 actuator_motors(100 Hz) ↔ gz 관절 충격 시각·패턴.
- `../imu_cause_20261014/prev_supplement/ekf_deep.py` ad410c38… → `ekf_deep_{d7_flat_a,d7_flat_b,d7_slope_a,d8_flat500}.json`: EKF 출력/지평 속도 − truth, 시간 이동 적합, Δpitch, 정지 뒤 극값.
계산 파라미터: 진행 방향 단위벡터 = fin−1 s pose 중앙 차분 속도; 중력 ENU (0,0,−9.8), a = R(q_pose)·f + g; 관절 가속도는 스텝 끝 stamp 에 귀속; 충격 임계 = 4×중앙값|Δv|; 관절→차체 부호는 fin−1 truth 속도와 맞춤.
