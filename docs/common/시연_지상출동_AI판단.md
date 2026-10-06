# 시연: 불 발견 → 소방차 출동 (feat/demo-ground, PR 하지 않음)

> 미완성 부분을 숨기지 않는다: 소방차는 물을 쏘지만 **불이 꺼지지는 않는다** (환경 진화 효과 ENV-07 미완).

## 1. 시나리오 (LIVE, `tools/demo_twin.sh`)

| 단계 | 내용 |
|---|---|
| 선택 전 | 출동 없이 **불만 번진다** (자동 정찰 끔, `ORCH_AUTO_RECON=0`) |
| 버튼 | 누를 때마다 트윈 전체를 14:45 신고부터 다시 띄우고, 불이 확인되면 아래가 자동 실행된다 |
| 공통 | 불 확인 → 총괄이 ① **화점 초기 진압** ② **보호선 2곳**(남전1리 마을회관·인제휴게소, 둘 다 사람 있는 시설) 출동 요청을 받아 차량을 고른다. 가장 가까운 소방차 **F-fire1**(Gazebo 가능)이 화점에서 방수(3000 L, 퍼포먼스 — 불은 안 꺼짐) → 물이 떨어지면 멈추고 거점으로 보충. 보호선 두 곳은 비슷한 위험이면 총괄이 **AI에 순서**를 묻고, 소방차가 모자라면 한 곳은 대기 |
| ① 본부 출동 (`hq`) | 정찰: **드론 전진 배치(B)**. 보호선은 **인제119 본부** 소방차(A-fire1, 약 5 km). UGV 는 멀어서 쓰지 않는다 |
| ② 인근 순찰차 출동 (`patrol`) | A-fire1 이 **인근 설악로 순찰 중**(노드 495015)이라 보호선에 빨리 도착. 드론은 **원통 기지(B′)** — 12 km 거리라 총괄이 더 가까운 **UGV 열화상**으로 첫 정찰을 보내고, 드론에 요청한 순찰은 드론이 **배터리 여유 부족(LOW_BATTERY)으로 스스로 거절**. 대신 UGV 3대(1대 + 추가 2대, sim)가 순찰을 메운다 — "드론 없이 UGV 여러 대가 기능하는가" 실험 |

재현(A/B/B′)은 미리 계산한 결과를 되감아 보는 화면이고 LIVE 와 별개다.

## 2. 실행

공통 준비: 저장소 루트 `.env` (커밋 금지) — `ORCH_LLM_PROVIDER=gemini`, `GEMINI_API_KEY=…`, `ORCH_LLM_MODEL=…`

### A. sim 만 (Mac, Gazebo 없이)

```bash
ENV_FORECAST_HORIZON_S=14400 ORCH_ENV_SENSE_TYPES=UAV,UGV UGV_FORWARD_ENGINE=1 UGV_DEMO_REAL_SPEED=1 \
TWIN_OPERATOR=0 TWIN_SPEED=10 UGV_TIME_SCALE=10 PY=$PWD/.venv/bin/python bash tools/demo_twin.sh
```

### B. F-fire1 을 Gazebo 로 (WSL, Gazebo 와 같은 기계에서 전부)

```bash
# 터미널 1 — PX4 + Gazebo (F-fire1 한 대, 인스턴스 4)
UGV_FORWARD_ENGINE=1 GUI=1 SPEED=4 ./ugv/tools/px4-start.sh F-fire1

# 터미널 2 — 트윈 (배속은 SPEED 와 같게 4. 실제 Gazebo 는 약 3.2배)
ENV_FORECAST_HORIZON_S=14400 ORCH_ENV_SENSE_TYPES=UAV,UGV UGV_FORWARD_ENGINE=1 UGV_DEMO_REAL_SPEED=1 \
UGV_DRIVER=px4 UGV_PX4_RESOURCES=F-fire1 \
TWIN_OPERATOR=0 TWIN_SPEED=4 UGV_TIME_SCALE=4 PY=$PWD/.venv/bin/python bash tools/demo_twin.sh
```

- WSL 저장소도 `feat/demo-ground` 이어야 하고, `.env` 는 git 에 없으니 따로 복사한다.
- Gazebo 차는 2 m/s → 330 m 를 약 1분(실제 시간)에 도착. `UGV_DEMO_REAL_SPEED` 는 Gazebo 차에는 적용되지 않는다.
- A-fire1 이 F-fire1 방수 중에 먼저 도착하면 `UGV_DEMO_FIRE_KMH=40` 처럼 낮춰 "보충하러 간 사이 도착" 이 되게 맞춘다.

브라우저 `http://localhost:8080/inje3d#live` → 왼쪽 아래 패널.

**`tools/demo_twin.sh` 로 띄우면 시나리오 버튼 = 처음부터 다시.** 버튼을 누르면 트윈 전체(Gazebo 모드면 Gazebo/PX4 도)를
새로 띄우고, 페이지가 LIVE 로 다시 열리고, 불이 확인되면 고른 시나리오가 자동 실행된다 (sim 약 15초, Gazebo 는 더).
실행 중에 다른 버튼을 눌러도 같다. 새로고침은 화면만 다시 그린다 (다른 사람이 보는 중에 시뮬레이션이 리셋되지 않게).
`run_twin.sh` 로 직접 띄우면 버튼은 지금 상태에 임무만 더한다.
B(Gazebo) 에서 `demo_twin.sh` 를 쓰면 터미널 1(px4-start)은 필요 없다 — 스크립트가 Gazebo 를 같이 띄운다.

| 변수 | 왜 |
|---|---|
| `ENV_FORECAST_HORIZON_S=14400` | 트윈 한 스텝(2100 s)이 기본 예측 범위(1800 s)보다 길어 위험 칸이 0개 → 묶음·AI 가 안 생김 |
| `ORCH_ENV_SENSE_TYPES=UAV,UGV` | 자동 기상 측정 임무가 화점 옆 소방차를 가져가면 도착 즉시 물을 다 쏟는다. 소방차를 빼 둔다 |
| `UGV_FORWARD_ENGINE=1` | 전진 배치 소방차 F-fire1 을 자원에 넣는다 |
| `UGV_DEMO_REAL_SPEED=1` | sim 차 속도 상한 소방차 60 km/h · UGV 30 km/h (Gazebo 차 제외) |
| `TWIN_OPERATOR=0` | 일몰 뒤 자동 순찰 요청 끔 |

## 3. 화면에서 볼 것

- 패널 "① 공통 ✔ 산불 신고 → A-uav1 정찰로 13_101 불 확인"
- 차량 이름표: `🚒 출동 중` → `💧 진압 중 · 물 2279 L` → `물 보충 중` → `대기 · 물 3000 L`
- (2대) AI 추천 순서·근거, "AI에 보낸 입력/받은 출력" 에 ① 시스템 지시 ② 사실 ③ JSON 스키마 ④ 응답
- 총괄 판단 화면 `http://localhost:8200/board`

## 4. 정직하게 말할 것 (미완성)

1. **불이 꺼지지 않는다.** 물 사용량·보충은 차량 장비 모의뿐. 진화 효과는 환경팀 계약(ENV-07, 근거 있는 효과 계수 필요)으로 남겼다.
2. **"순찰 중 발견"이 아니라 "신고 → 정찰 확인"** 이다. 자유 순찰 경로는 없다.
3. 전진 배치 거점 F 는 시연용 가정 (실제 소방 거점 아님).
4. AI 는 비슷한 위험의 임무 순서만 정한다. 출동 가능 여부·안전 검사는 규칙이 한다. AI 가 실패하면 규칙 순서로 간다.

## 5. UGV(지상 자원)가 출동하려면 필요한 것 — 이번에 성공시키며 확인한 조건

| # | 조건 | 없으면 |
|---|---|---|
| 1 | 임무의 허용 자원에 지상 자원이 있다 (`resource_types` 에 `UGV`/`FIRE_ENGINE`) | 드론만 후보 → 드론이 간다 |
| 2 | 요구 센서를 지상 자원이 가진다. 소방차는 센서 없음 → `sensor: null`. UGV 열화상은 `ORCH_UGV_THERMAL=1` 일 때만 | `REQUIRED_CAPABILITY_UNAVAILABLE` 로 후보 제외 |
| 3 | 목표 좌표가 도로 노드에서 `TARGET_SNAP_M` 안 (산속 칸은 안 됨) | Local REJECT `TARGET_UNREACHABLE` |
| 4 | 그 자원이 비어 있다 (다른 임무·물 보충·주행 중 아님) | `OCCUPIED`/`BUSY` → 대기(HOLD), 비면 자동 재배정 |
| 5 | 후보 순서는 직선거리 → 지상 자원이 드론보다 멀면 드론이 먼저. 지상으로 보내려면 드론이 못 가거나(강풍 REJECT·사용 중) 허용 자원에서 드론을 뺀다 | 드론이 가져감 |
| 6 | UGV 서버가 총괄과 연결돼 있고(`:8100`) 같은 시간배율(`UGV_TIME_SCALE` = 트윈 배속) | 평가 실패 또는 ETA 어긋남 |
| 7 | 자동 기상 측정이 지상 차량을 가져가지 않게 (`ORCH_ENV_SENSE_TYPES`) | 소방차가 기상 측정 나가서 물을 쏟고 옴 |
| 8 | (AI 순서까지 보이려면) 비슷한 위험의 대기 임무 2건 이상 + 위험 칸 존재(`ENV_FORECAST_HORIZON_S`) + API 키·사용 가능한 모델 | 규칙 순서로만 출동 |

## 6. 바뀐 파일 (이 브랜치)

| 파일 | 내용 |
|---|---|
| `orchestrator/config.py`, `llm.py` | Gemini 어댑터 (`ORCH_LLM_PROVIDER=gemini`, 과부하 503 재시도), `ORCH_ENV_SENSE_TYPES` |
| `orchestrator/engine.py` | 자동 기상 측정 허용 자원을 설정값으로 |
| `orchestrator/api.py` | `/view/risk_cells`, `/priority/group_of/{id}`, `llm.last_plan`(지시·입력·스키마·응답·오류), 배정 경합 때 AI 호출 |
| `ugv/config.py` | `UGV_FORWARD_ENGINE`(F-fire1), `UGV_DEMO_REAL_SPEED`, 물 보충 설정 |
| `ugv/server.py` | 물 부족 시 거점 경유 보충 후 출동, 물이 떨어지면 스스로 거점 복귀·보충 (`UGV_AUTO_RTB_REFILL`) |
| `ugv/tools/build_road_network.py`, `ugv/data/road_network.json` | 거점 F(노드 494957 → `F`), F-fire1 스폰 자세 |
| `tools/run_twin.sh` | `UGV_DRIVER` 를 밖에서 지정 가능 |
| `web/app.py`, `web/static/inje2019/index.html` | 시연 패널(공통 단계 + 2개 시나리오), AI 판단 기록, 차량 상태·Gazebo 표시, 버튼 = 재시작+자동 실행 |
| `tools/demo_twin.sh` | run_twin.sh 감시: 버튼 누르면 트윈(+Gazebo) 전체 재기동, 불 확인 뒤 시나리오 자동 실행 |
