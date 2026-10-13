# 실제 지형 ab_route_v1 짧은 선별 1회 — 사전 실행표 (2026-10-14 08:0x, 실행 전, Codex 0755 3절)

## 진입 조건
S5 운영 조합 확인 (ops5) **2/2 PASS** 뒤에만 자동 시작 (chain_screen1.sh 가 chain_ops5.out 의 `CHAIN_OPS5_DONE … 2/2 PASS` 확인, 아니면 HOLD), 서버 03d5b5d·차량 48f3e5f HEAD, 이 표 해시 (SCREEN1_freeze.sha1) 확인. 장거리 A↔B 는 이 선별 결과 보고 뒤.

## 고정 자산 (해시)
- 월드 tiles_v2/ab_route_v1.sdf, 부분집합 road_subset_ab_route_v1.json (도로 506), tiles.json 8d702d48 (타일 재생성 없음), 선택 160 타일 (route_tile_union_v2.json) — 해시는 SCREEN1_freeze.sha1.
- 정적 검사 (기존, Codex 독립 재계산 일치): 네 경로 제외 도로 0·월드 부분집합 누락 0·경계 25 m 밖 선분/차체/끝 60 m 0 (check_ab_world_v2.json), 이음매 275 쌍 최대 0.0071 m.
- 스폰: A-ugv1 (3992.08, 5606.28, z 27.574 = 지면 + 0.45, yaw −2.3835 → heading 226.564°) — screen_A_ugv_spawn.txt / screen_A_ugv_fleet.json (gz_world ab_route_v1). 방법 검증: 같은 높이장으로 s3113 기록의 원점 z − 지면 = −0.007~+0.004 m.
- 후보·운영 조합 = ops5 와 같음: 서버 03d5b5d, 차량 susp_a_acc3_imu500, CAP_FIRST 1·ITEMS_RAMP 1·END_EXTEND 1·STALL_DETECT 1·다른 후보 0, 서버 TEST_HOOKS 0 (run_sc_v10_ops), park 1.0 s.

## 구간 (screen_segment.py → screen_A_ugv.json, A→B UGV 경로 앞부분)
- 거점 A 출발 → 경로 누적 **2,382 m** 지점 (5223.31, 6880.96) = lat 38.073175, lon 128.182170 (`--target`). 타일 T04_16 → T05_16 (이음매 s=1,050 m) → T05_17 (이음매 s=2,205 m), 마지막 이음매 뒤 177 m 정지 여유.
- 구간 정적 특성 (5 m 간격): 경사 −6.94 %~+1.52 % (|경사| p95 1.76 %, **6 % 초과 20 m — 시험된 하강 3~6 % 밖**, 내리막), 횡경사 |max| 2.83 % (p95 0.49 %), 높이 21.3~28.7 m, 속도 상한 최대 16.67 m/s (60 km/h). 160 타일 전체 경사/횡경사 정적 검사는 **미실행 (미완료로 표시)** — 이 구간만 수행.

## 회차 판정 (ts1_screenA_ugv_a)
**제품 게이트 — screen_judge.py** (= e4_judge_ops; 사례 screenA 는 E3 경계 값 대조 없음): 래퍼 유효, 1 증거 (END_EXTENSION 3.0·RA_ACC_RAD_MAX 3·park 1.0/test_hook false), 2 서비스 목적지 ≤ 1.0 m, 3 seq 끝 도달·단조, 4 judge3 (도로 경계·도착·정지), 5 정지 뒤 30 s ≤ 0.1 m, 6 PX4 자체 정지, 7b~7e 물리 정지·유지·park 정책·RUNAWAY/CUT 없음, 8 ARRIVED ≤ 1.0, 0e 500 Hz, 0h STOP_PATH 없음, 0i 운영 env. 비PASS 면 선별 실패 → 원인 확인, A↔B 진행 안 함.
**접지·차체 (screen_ground.py, gz 기록 pose)** — 사전 기준: 주행 전 구간 모델 원점 z − 지면 ∈ [−0.10, +0.10] m (s3113 근거 −0.007~+0.004), 정지 때 |z − 지면| ≤ 0.03 m, 이음매 두 곳 통과 (tiles_seen 에 3 타일). 기록 없으면 미확인.
**성능 (rtf_mem_probe.sh, 5 s)** — **특성 측정** (기존 운영 상한 없음): 월드 로드 전후 WSL 메모리, 주행 중 RTF 중앙값·최소, sim 시간 진행. 결과 뒤 임계값을 만들어 합격시키지 않음. RTF 가 지속적으로 < 0.5 이면 장거리 전 보고·판단 요청 (사전 표시만).
**기타 기록**: 래퍼 시작 문서 (prov·verify — 실제 해석 월드/모델 해시), 잔존 프로세스 수 (사후), 실제 500 Hz, 위치 기록 신선도 (judge 표본 공백).

## 중단
선별 1회 결과를 오퍼스가 정리해 Codex 보고. 타일 로드·접지·기록·정지·경계 게이트 문제면 멈추고 원인 확인. 소방차는 별도 (UGV S5 결과 자동 적용 안 함).

## 08:3x HOLD (Codex 0814 2절)
원안 그대로 실행하지 않음 (범위·속도·−6.94 % 가 최초 선별로 큼). 미기동. 대신 terrain_ab/ENVAB_criteria.md (단계 A 정지 확인 → 단계 B 300 m·20 km/h·|경사| ≤ 3 %). 이 폴더의 screen_judge.py 는 c7 증거 절단 규칙 이전 사본 — 재사용 금지.
