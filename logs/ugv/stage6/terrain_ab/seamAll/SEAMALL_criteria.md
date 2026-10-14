# 전 타일 보정 월드 주행·정차 진단 4 회 — 사전 기준 (2026-10-14, 실행 전, 사용자 지시)
공통: 지형 tiles_v2c1 (616 타일 보정, 정적 게이트 PASS), 차량 48f3e5f susp_a_acc3_imu500, NO_PX4 (구동 = seamC/r2_drive.py motor_speed 1 m/s 2 s 램프, 조향 0), 파티션 adair_susptest, 기록기 seamC/gz_detail_seam.py (중단 신호 그대로). 해석 증거 매 회차: AABB 500×160·499.512×0·prov 'stage5/tiles_v2c1/' 160 (아니면 invalid_evidence). 스폰 all_spawn_calc.json (z = 지면 + 0.45).
| 회차 | 내용 | 판정 |
|---|---|---|
| a1_revX | X 경계 4380 을 **반대 방향** (T04_16 → T05_16), yaw 0.5764, 1 m/s 15 s | r2_check_gen (AXIS x, BND 4380, DIR +1, T04_16→T05_16) |
| a2_obliqX | X 경계 **45° 비스듬히**, yaw π/4, 1 m/s 18 s | 같음 |
| a3_stopY | Y 정확 경계 (앞바퀴 y −4631.000) **15 s 정차 → 1 m/s 10 s 재출발 → 정지 유지** | r2_check_gen (AXIS y, BND −4631, DIR +1, 접촉 상대 'T16_'→T16_06 — 앞바퀴가 처음부터 경계에서 T16_06 접촉이라 '변화' 조건은 약하게 지정, 기록으로 보완) |
| a4_corner | 네 타일 모서리 정지 (FL 모서리·FR Y 띠·RL X 띠) 30 s | seam_check_c1b (기존 정적 건전성 기준, ft/fn ≤ 0.10 포함) |
r2_check_gen PASS = 기록기 rc 0·표식 없음·AABB·구동 기록·실제 0.8~1.2 m/s·방향 ≤ 10°·네 바퀴 경계 0.6 m 넘어 통과·접촉 상대·구동+정지 VALID ≥ 95 %·자세 ≤ 2° (정착 포함)·바퀴 높이 [0.29, 0.41]·서스펜션 < 0.098·지속 함몰 |Δdz| ≤ 0.03·정지 속도 < 0.05.
진단 묶음: 판정 FAIL 은 기록하고 다음 회차 진행 (a3·a4 는 0.19 mm 띠로 FAIL 가능 — 작다는 이유로 무시하지 않고 정차·재출발 영향 확인이 목적). 표식·출력 누락이면 멈춤. 기준 사후 변경 없음.
