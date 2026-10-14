# 실제 지형 제한적 환경 선별 — 단계 A·B 사전 기준 (2026-10-14 08:3x, 실행 전, Codex 0814 2절)

**운영 S5 승격과 분리한 환경 검증.** 경사 운영 '차단 전 1 초 자체 정지' 미확인을 PASS 로 보는 예외 아님. 원안 screen1 (2.38 km·60 km/h·−6.94 %) 은 **HOLD** (미기동, 자기 소유 — chain_screen1.sh 는 실행하지 않음; 그 판정기 사본은 c7 증거 절단 규칙 이전 사본이라 쓰지 않음).

## 공통 고정
서버 03d5b5d, 차량 48f3e5f susp_a_acc3_imu500, 운영 조합 (CAP_FIRST 1·ITEMS_RAMP 1·END_EXTEND 1·STALL_DETECT 1·다른 후보 0, 서버 TEST_HOOKS 0 = run_sc_v10_ops, park 1.0 s), 월드 tiles_v2/ab_route_v1.sdf + road_subset_ab_route_v1.json (sha1 50e2f798) + tiles.json 8d702d48 (지형 tiles_v2 그대로). **임시 선별 프로필: UGV_MAX_SPEED_KMH=20** (config.MAX_SPEED_MPS → profile.max_speed — S5 의 60 km/h 조합과 다름, 해시·env 로 구분). gz 기록기 (run_sc_v9 계열 GZ_REC_MODEL) + rtf_mem_probe (5 s).
스폰 segB_spawn.txt: (4420.688, 5954.475, z 29.091 = 지면 28.641 + 0.45, yaw −2.5652) = B→A UGV 경로 s 36,415 m 지점, 진행 방향.

## 구간 선정 (seg_search_b.py → seg_search_b.json, 오프라인)
규칙: UGV 두 경로에서 길이 200~400 m, 이음매 ≥ 1 (시작 뒤 ≥ 50 m, 끝 앞 ≥ 80 m), 앞 20 m·뒤 40 m 포함 **|종단경사| ≤ 3 %** — 후보 54. 선택 = B→A s 36,415 → 36,715 (300 m), 이음매 T05_16 → T04_16 (s 36,465, 시작 뒤 50 m), |경사| max 0.81 % (p95 0.80 %), |횡경사| max 0.95 %. 정적 포함: 이 구간은 check_ab_world_v2 의 B→A 전 경로 검사 (경계 25 m 안 선분·차체·끝 60 m 0, 제외 도로 0) 안에 있음.
서버 계획 오프라인 확인 (plan_check_b.py, 서버 트리 03d5b5d dirty 0, 20 km/h): ACCEPT, 계획 293.9 m, 도로 682500154 → 682500153 → 682500726 (기대 경로와 같은 도로), 미션 항목의 기대 경로 이격 ≤ 0.03 m (점-선분), 계획 속도 상한 5.556 m/s, 목적지 682500726 s 82.48. (첫 판 이격 20.6 m 는 점-꼭짓점 측정 결함 — 고침.)

## 단계 A — ta1_idle_segB (미션 전송 없음, 90 s 정지, 주행 합격 아님) — envA_check.py
래퍼 rc 0·표식 없음 / 준비 위치 ↔ 스폰 ≤ 2 m / 서버 폴링 45 회 중 ≥ 40 READY·sim 시각 증가·갱신 나이 ≤ 2 s / 접지 (처음 5 s 제외) |원점 z − 지면| ≤ 0.03 m·|롤|,|피치| ≤ 2° (구간 경사 < 1 %) / 사후 잔존 0. 메모리·RTF 는 특성 기록 (RTF 중앙값 < 0.5 면 보고 표시). 하나라도 FAIL/미확인이면 B 안 함.

## 단계 B — tb1_segB_ugv_a (300 m 정상 도착, 20 km/h) — envB_judge.py + envB_extra.py
- 제품 게이트 envB_judge = 운영 도착 판정기 (e4_judge_ops, 7c 증거 절단 = UNCONFIRMED 포함) 그대로, 사례 segB (E3 경계 값 대조 없음): 1 증거·2 목적지 ≤ 1.0 m·3 seq·4 judge3 경계/도착/정지·5 30 s ≤ 0.1 m·6 자체 정지·7b~7e·8 ARRIVED ≤ 1.0·0e 500 Hz·0h STOP_PATH 없음·0i 운영 env.
- 추가 envB_extra: 속도 제한 실제 적용 (health.env UGV_MAX_SPEED_KMH "20", 준비 profile max_speed_kmh 20, Gazebo 실제 최고 ≤ 6.1 m/s), 접지 (전 구간 z − 지면 ∈ [−0.10, +0.10], 정지 |·| ≤ 0.03), 이음매 통과 (T05_16·T04_16 둘 다).
- 예기치 않은 STOP_PATH/FAULT/CUT/자료 누락 = 선별 비PASS 로 보존. 감독·차단은 끄지 않음 (서버 감독·PX4 failsafe·래퍼 사후 정지 그대로).
- 통과해도 원안 2.38 km/60 km/h·가파른 구간·A↔B 는 별도 게이트. 자동 후속 없음.
