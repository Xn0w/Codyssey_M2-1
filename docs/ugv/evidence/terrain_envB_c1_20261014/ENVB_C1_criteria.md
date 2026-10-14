# A 단계 — 원 B 조건 + 후보 c1 재실행 1 회 사전 기준 (2026-10-14 09:5x, 실행 전, Codex 0940 2절 A)

## 단일 차이
원 tb1_segB_ugv_a 와 **같은** 서버 03d5b5d·차량 48f3e5f susp_a_acc3_imu500·운영 조합 (CAP_FIRST 1·ITEMS_RAMP 1·END_EXTEND 1·STALL_DETECT 1·다른 후보 0, 서버 TEST_HOOKS 0, park 1.0 s)·임시 선별 프로필 UGV_MAX_SPEED_KMH=20·월드 ab_route_v1·부분집합·스폰 segB_spawn.txt·목표 (38.06325574385999, 128.17025179536637)·track-s 240·post-stop-s 35·step·센서. **차이 = 후보 c1 (T04_16·T05_16 collision X/Y size 1000.9765625) 만** — 래퍼 run_sc_v11_c1.sh (= v10_ops + CAND_ROOT 를 모델 검색 앞에, 기동 뒤 해석 증거).
해석 증거 (기동마다, 아니면 invalid_evidence·종료 7): gz 로그 AABB 반폭 500 = 2 줄·499.512 = 158 줄, run_provenance 의 T04_16·T05_16 dir 이 seamC/tiles_c1 (2 개) — aabb_<TAG>.json. 나머지 158 타일은 원본 tiles_v2 (prov 의 dir·해시).
추가 계측: 시험 명령 (testcmd.sh) 이 road_test 전에 고율 기록기 gz_detail_seam.py (파티션 adair_ugv, 330 s; 바퀴별 접촉 상태·상대·서스펜션 q·link 위치, 중단 신호 = 기록만 멈춤) 를 띄움. 기존 gz 기록기 (GZ_REC_MODEL) ·rtf_mem_probe·전율 로거 그대로.

## PASS = 세 판정 모두 PASS + 래퍼 rc 0 (원 기준 완화 없음)
1. **envB_judge.py** (원 운영 도착 판정 그대로, 접두 tb2_): 1 증거·2 목적지 ≤ 1.0 m·3·4 judge3·5 30 s ≤ 0.1 m·6 자체 정지·7b~7e (7c 증거 절단 = UNCONFIRMED)·8·0e 500 Hz·0h STOP_PATH 없음·0i 운영 env.
2. **envB_extra.py** (원 추가 판정 그대로 + bool 정규화): 속도 제한 실제 적용 (env 20·profile 20·Gazebo 최고 ≤ 6.1 m/s), 접지 (전 구간 원점 z − 지면 ∈ [−0.10, +0.10], 정지 |·| ≤ 0.03), 이음매 통과 (T05_16·T04_16).
3. **detail_check.py** (신규, 기록 시작 + 5 s 이후): 기록기 행 > 100·중단 신호 없음·서스펜션 발행, 네 바퀴 접촉 VALID ≥ 95 %, 바퀴 link z − 분석 지면 ∈ [0.29, 0.41], 서스펜션 |q| < 0.098, 네 바퀴 접촉 상대 T05_16 → T04_16 순서.
FAIL/UNCONFIRMED 면 다음 단계 (B: 4 타일 묶음) HOLD·원인 확인. 같은 조건 자동 반복·마찰/엔진/서스펜션 동시 변경 없음.
