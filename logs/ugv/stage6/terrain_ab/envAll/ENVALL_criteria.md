# 전 타일 보정 월드 회귀 — 사전 기준 (2026-10-14, 실행 전, 사용자 최우선 지시)
- 지형 = **tiles_v2c1** (make_tiles_c1.py: tiles_v2 616 타일 전부 collision size X/Y 1000 → 1000·1025/1024, visual·pose·PNG·수직 불변). 전체 정적 게이트 all_static_gate.json **PASS** (타일 616 검사 실패 0, 공유 가장자리 1,182 틈 0·높이 차 ≤ 8.4 mm, 모서리 567 ≤ 6.2 mm).
- 조건 = 원 B (tb1_segB_ugv_a) 와 같음: 서버 03d5b5d (park 1.0 기본 — 운영 정차 후보 미혼합), 차량 48f3e5f susp_a_acc3_imu500, 운영 조합, UGV_MAX_SPEED_KMH=20, segB 스폰·목표·300 m. **차이 = 월드 지형 (2 타일 → 160 타일 전부 보정)**.
- 해석 증거 (run_sc_v12, 아니면 종료 7): gz 로그 AABB 반폭 500 = **160**·499.512 = **0**, run_provenance 타일 dir 'stage5/tiles_v2c1/' = **160**.
- PASS = 래퍼 rc 0 + envB_judge (원 운영 도착 판정) + envB_extra (속도 제한·접지·이음매 T05→T04) + detail_check_v2 (네 바퀴 VALID ≥ 95 %·바퀴 높이·서스펜션·T05→T04·기록 범위·준비 게이트·감시 없음). 판정 순서 = 수집 → slope_report → 판정 (A 순서 결함 반영).
- 알려진 미해결: 정확 경계 정지의 0.19 mm 무소유 띠 (Fable 가설) 는 이 회차 판정 범위 밖 (주행 통과). 다음: 역방향 저속 1 회 (별도 동결).
