# 진단 8 — IMU update_rate 500 Hz 단일 개입, 평지 1회 (Codex 0605) — 사전 고정 (2026-10-14 06:04:34, 실행 전)

**진단이며 제품 채택 아님.** 한 회차 결과로 원인·최종 안전성을 확정하지 않는다. 결과별 후속은 Codex 0605 5절 그대로 (자동 추가 회차 없음).

## 단일 변경·고정
- 변형 `susp_a_acc3_imu500` (ADAIR_wt_vehicle 48f3e5f): susp_a_acc3 와 adair_ugv/model.sdf **imu_sensor update_rate 250 → 500 한 줄만** (다른 파일 바이트 동일, model sha1 b8f35590 / 기준 cf71aa0b). 정식 모델 불변. PX4 IMU_INTEG_RATE 은 현재값 그대로 (250) — 바꾸지 않음.
- 그 밖 = 진단 7 평지 b: 서버 ADAIR_wt_hook 03d5b5d, 플래그, 물리 2 ms, 컨트롤러·서스펜션·마찰·노이즈·EKF·F1/STOP_ITEMS_RAMP·park/감독, 같은 s0547 x·y (kangwon_flat, z 0.45), 같은 road_test 인자, 같은 전율 logger_topics.txt (회차 동안만 설치), gz 기록기. 새 ID d8_flat500_s0547_a, 단독·직렬. 실행 스크립트 run_flat_v9.sh.
- 동등성 허용 (진단 7 평지 b 기준): 중단 때 속도 9.1~9.5 m/s, 정지 경로 needed 33.5~35.5 m, 정지 항목 수 같음. 밖이면 '조건 다름' 으로 표시하고 순수 표본화 효과라 하지 않는다.

## 적용 확인 (실패 = 적용 미확인, 후속 중단)
- gz IMU stamp 간격 중앙값 2 ms, PX4 sensor_accel timestamp_sample 간격 2 ms (≥ 450 Hz, 누락 < 1 %). vehicle_imu / sensor_combined 의 dt·출력률·적분 표본 수 (기대: 4 ms 에 2 표본 — 기록으로 확인). 실제 RTF·actuator_motors 주기·관절·정지 위치 기록.

## 지표 (부호 E = IMU Δv − truth Δv, 음수 = 과대 감속, W1 [fin−2.5, fin−0.05], gz 모델 자세)
1. **E500** (500 Hz 전체 표본, diag7_evidence_v2.py): |E500| ≤ 0.15 m/s 인지 + 정지·순항 창 같은 분석기.
2. **E250_even / E250_odd** (같은 500 Hz 자료의 짝/홀 2 ms 표본만, 4 ms 적분 반사실, --virtual250): 큰 반대 부호 편차면 위상 의존 표본화 가설의 강한 근거. 폐루프 250 Hz 결과로 표시하지 않음.
3. 20 ms 위상별 평균·적분 기여 (충격 소멸이 아니라 누적 편향 감소 여부).
4. 단계 전달 (gz raw500 → PX4 raw500 → vehicle_imu/combined Δv), EKF 피치 오차·정지 뒤 부호 속도, park 표본·분기, 정지거리·30 s·감독 여유 (기록·보조, 제품 판정 아님).
- 확인: 진단 7 평지 b ULog 의 IMU_INTEG_RATE 등 (아래) 을 그대로 둔다.
