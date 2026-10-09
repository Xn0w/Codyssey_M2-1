# UGV Local Agent API 정의서

| 항목 | 값 |
|---|---|
| 버전 | 0.1.0 |
| Base URL | 로컬 `http://localhost:8100` |
| 형식 | JSON, UTF-8 |
| 단위 | 거리 m, 시간 s, 연료 %(0~100), 좌표 WGS84 |
| 코드 | `ugv/server.py`, `ugv/api_models.py` |
| 문서 (자동) | `http://localhost:8100/docs` |

## 실행

```bash
pip install fastapi uvicorn
UGV_DRIVER=sim uvicorn ugv.server:app --port 8100     # PX4 없이 (좌표 계산 주행)
UGV_DRIVER=px4 uvicorn ugv.server:app --port 8100     # UGV_PX4_RESOURCES 자원만 PX4, 나머지 sim
GUI=1 ./ugv/tools/px4-start.sh 0                       # PX4 SITL rover (gz_r1_rover) + Gazebo 창
```

| 환경변수 | 기본값 | 의미 |
|---|---|---|
| `UGV_DRIVER` | `sim` | `sim` 또는 `px4` |
| `UGV_PX4_RESOURCES` | `A-ugv1` | px4 모드에서 PX4 에 연결할 자원 (쉼표 구분) |
| `UGV_TARGET_SNAP_M` | `2000` | 화재에서 가장 가까운 도로 노드가 이보다 멀면 `TARGET_UNREACHABLE` |
| `UGV_APPROACH_FALLBACK` | `0` | `1` 이면 가장 가까운 노드로 못 갈 때 다음 노드로 접근 |
| `UGV_ENV_URL` | `http://127.0.0.1:8300` | 환경 서버. UGV 시계가 환경 시각(`/health` simulation_time_s)을 따라가고, 상황판은 시나리오 시각(scenario_start_kst + 초)으로 보인다. 처음 연결하면 환경 시각에 멈춰 있다가 환경이 한 스텝 나아가거나 차가 처음 출발하면 흐른다. 비우면 혼자 (서버 시작 = 0) |
| `UGV_TARGET_MODE` | `node` | `road_point` 이면 `target`(좌표)을 노드 대신 가장 가까운 **도로 위 점**에 붙여 거기 선다. 요청마다 `target_mode` 로도 고른다 |
| `UGV_APPROACH_MAX_M` | `500` | fallback 접근 노드의 화재 거리 상한 |
| `UGV_TIME_SCALE` | `1` | 시뮬레이션 초 / 벽시계 초. PX4 쪽 `PX4_SIM_SPEED_FACTOR`(px4-start.sh 의 `SPEED`)와 같은 값. sim 차량도 이 배율로 달린다 |
| `UGV_SECONDS_PER_ENV_STEP` | `60` | 환경 CA 1스텝이 몇 시뮬레이션 초인가. **잠정값 (INT-05 미정)** |
| `UGV_ORCH_URL` | `http://127.0.0.1:8200` | 총괄 주소. 상황판 출동 요청을 여기 `POST /tasks` 로 전달 |
| `UGV_HISTORY_DIR` | `ugv/.state/history` | 실행 기록 폴더. `UGV_STATE_DIR` 과 따로 둔다 (run_twin 은 실행마다 새 STATE_DIR) |
| `UGV_HISTORY` | `1` | 실행 기록 (`{UGV_STATE_DIR}/history/<run_id>.jsonl`, 도로 상황판 재생용). `0` 이면 끔. 보관 개수 `UGV_HISTORY_KEEP`(30) |
| `UGV_REPORT_URL` | (빈 값 = 끔) | 총괄 주소(예 `http://127.0.0.1:8200`). 주면 이벤트마다 `POST {URL}/events` 로 보고. 기본은 총괄 조회(polling)만 쓴다 |
| `UGV_SCENARIO` | (없음) | 도로 환경 시나리오 (CSV/JSON). 기본은 시나리오 없음 — 도로 전부 열림. 예) `ugv/scenarios/inje_girin.csv` |

## 구조

- 서버 1개가 지상자원 전부(`ugv/config.py` 의 `RESOURCES`)를 맡는다. UAV 는 기체 1대당 서버 1개지만, UGV 는 자원들이 도로망 그래프 하나를 공유해야 도로 차단이 모든 자원의 판단에 동시에 반영된다.
- 도로망은 환경 데이터(`environment/data/processed/roads_reprojected.gpkg`, EPSG:5186)를 변환한 `ugv/data/road_network.json` (노드 534, 도로 672, 184 km, 도로 선형 포함). 거점 노드 id 는 `A`(인제119), `B`(기린119) — 좌표는 주소로 추정.
- 모든 시각·ETA·속도는 **시뮬레이션 초** 기준 (`ugv/sim_clock.py`). 환경 스텝을 `POST /clock/env` 로 받으면 거기에 맞춘다.
- 도로 환경(차단 도로·경유 불가 노드·혼잡)은 UGV 것이고 환경 모듈과 별개다. 시나리오 파일의 시간대가 정하고, `/roads/*` API 로 덧붙일 수 있다. 화재는 도로를 막지 않는다 (팀 결정).
- 차량은 노드 사이 직선이 아니라 **도로 선형을 따라** 달린다 (`ugv/route_plan.py`). 주행 중 남은 경로가 막히면 지금 도로 끝에서 재탐색한다.
- 도로 노드 id 는 UGV 내부 값이다. 호출측은 위경도로 요청하고, 응답의 `target_node` 로 실제 목적지를 확인한다.

## 엔드포인트 요약

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/health` | 드라이버 모드·자원·도로망·접근 규칙 확인 |
| GET | `/ugv?base=A` | 거점별 자원 상태 목록 |
| GET | `/ugv/{resource_id}/state` | 자원 1대 상태 |
| POST | `/ugv/{resource_id}/evaluate` | 수행 가능성 판단 (**움직이지 않음**) |
| POST | `/ugv/{resource_id}/execute` | 주행 시작 (**Safety ALLOW 이후에만 호출**) |
| POST | `/ugv/{resource_id}/stop` | 주행 중지 |
| GET | `/ugv/{resource_id}/task/{task_id}` | 주행 진행·결과 |
| GET | `/ugv/{resource_id}/observation` | 현재 위치의 도로 상태 관측 |
| GET | `/graph/nodes/{node_id}` | 도로 노드 좌표 |
| GET | `/roads` | 막힌 도로(출처 포함)·경유 불가 노드·혼잡 도로 |
| POST | `/roads/{road_id}/block` | 도로 직접 차단·해제 `{"blocked": true}` (출처 `manual`) |
| POST | `/roads/nodes/{node_id}/block` | 노드 경유 불가·해제 — 닿은 도로 전부 차단 (출처 `manual`) |
| POST | `/roads/closures/cells` | 격자 칸 묶음 구역 통제 (예전 `/env/fire_cells`, 출처 `cells`) |
| POST | `/roads/congestion` | 혼잡 직접 설정 |
| GET | `/roads/geometry?only_changed=true` | 시각화용 도로 선형 + 차단·혼잡 |
| GET | `/ugv/{resource_id}/route` | 주행 중 경로 선형·남은 거리/시간·재탐색 횟수 + `legs`(구간별 도로·거리·소요시간·혼잡·DONE/CURRENT/NEXT) |
| GET | `/graph/bases` | 거점 노드 (상황판 표시용) |
| GET | `/graph/edges` | 도로 전체 (양 끝 노드·이름·길이) — 상황판 그래프 보기 |
| GET | `/graph/nodes` | 도로 노드 전체 + `degree`(닿은 도로 수, 2 가 아니면 교차로·끝점) |
| GET | `/view/vehicles` | 상황판 차량 요약: 상태 + 지금 임무(목적지·단계·남은 시간·작전 이유) + 지금 자리(노드 또는 도로 A→B) |
| POST | `/view/command` | 상황판에서 **차를 골라** 노드를 누른 경우 — 그 차에 직접 명령 `{"resource_id", "node_id", "replace"}`. 임무 중이면 `replace=true` 일 때만 세우고 바꾼다 (총괄 Safety 미경유). `node_id` 대신 `point: {lat, lon}` 이면 도로 위 지점에 선다 |
| GET | `/view/terrain` | 지도 보기 배경용 지형 (환경 격자 고도·연료를 위경도 격자로) |
| POST | `/view/dispatch` | 상황판 노드 클릭 출동 `{"node_id", "resource_type": "UGV"\|"FIRE_ENGINE"}` → **총괄 `POST /tasks` 로 전달** (UGV 를 직접 움직이지 않음) |
| GET | `/view` | **UGV 도로 상황판** (브라우저로 연다) |
| GET | `/history/runs` | 실행(서버 기동) 목록, 최신 먼저 |
| GET | `/history/runs/{run_id}?after=seq` | 한 실행의 기록 (이어 받기) |
| GET | `/reports?limit=30` | 총괄에 보낸 보고 최근 목록·전송 통계 |
| GET | `/clock` | 시뮬레이션 시계 (시각, 배율, 환경 동기 상태) |
| POST | `/clock/env` | 환경 스텝 알림 `{"sim_step": n}` → 시계 동기. 스텝이 줄면 시나리오 재시작 |
| GET | `/scenario` | 시나리오 규칙, 지금 켜진 것, 다가올 것, 켜짐/꺼짐 기록 |
| POST | `/scenario/reset?sim_time_s=0` | 시계·시나리오 처음부터 (시연 반복용) |

호출 순서: `state` → `evaluate` → (총괄·Safety 판단) → `execute` → `task` 폴링

---

## GET /ugv/{resource_id}/state

| 필드 | 타입 | 설명 |
|---|---|---|
| `resource_id` | string | `A-ugv1`, `A-fire1`, `B-ugv1` |
| `resource_type` | string | `UGV` / `FIRE_ENGINE` |
| `base` | string | `A` / `B` |
| `state` | string | `READY` / `RUNNING` / `UNAVAILABLE` (주행 중 이상. `/stop` 으로 해제) |
| `position.lat` / `position.lon` | float | 현재 위치 |
| `fuel_pct` | float | 0~100. sim: 1 km 당 1% 감소, px4: 배터리 값 |
| `current_node` | string \| null | 노드에 정지 중일 때만 값. 주행 중 `null` |
| `current_task_id` | string \| null | 수행 중 task |
| `driver` | string | `sim` / `px4` |
| `driver_status` | string | sim: `IDLE`/`MISSION`/`ARRIVED`, px4: flight mode |
| `updated_at` | float | 마지막 위치 반영 시각 (epoch s) |
| `fault` | string \| null | `UNAVAILABLE` 일 때 이상 내용 `CODE: 설명` |
| `current_road_id` | string \| null | 주행 중 지금 달리는 도로 |
| `sim_time_s` | float | 응답 시점 시뮬레이션 초 |

없는 자원이면 `404`.

## POST /ugv/{resource_id}/evaluate

판단만 하며 차를 움직이지 않는다.

**요청** — `target` 과 `target_node` 중 하나

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `task_id` | string | ✅ | |
| `decision_id` | string | ✅ | 재평가마다 새 값 |
| `target.lat` / `target.lon` | float | | 화재 좌표 (권장) |
| `target_node` | string | | 도로 노드 id 를 이미 알 때 |

```json
{"task_id": "task-101", "decision_id": "dec-001", "target": {"lat": 38.0444, "lon": 128.2028}}
```

**응답 200**

| 필드 | 타입 | 설명 |
|---|---|---|
| `task_id`, `decision_id`, `resource_id` | string | 요청값 그대로 |
| `verdict` | string | `ACCEPT` / `REJECT` (COUNTER 없음) |
| `eta_sec` | int \| null | ACCEPT 일 때 도로망 기준 도착 예상 시간. REJECT 는 `null` |
| `reason` | string \| null | 아래 표 |
| `detail` | string \| null | 사람이 읽는 설명 |
| `target_node` | object \| null | 실제 목적지 도로 노드 `{node_id, lat, lon, snap_m}`. `snap_m` = 요청 좌표와의 거리 |
| `path` | string[] \| null | ACCEPT 일 때 경유 노드 id (출발 노드 포함) |

```json
{"task_id": "task-101", "decision_id": "dec-001", "resource_id": "A-ugv1",
 "verdict": "ACCEPT", "eta_sec": 436, "reason": null, "detail": null,
 "target_node": {"node_id": "494852", "lat": 38.043899, "lon": 128.202801, "snap_m": 55.6},
 "path": ["A", "495227", "...", "494852"]}
```

**판정 순서와 reason 코드**

| 순서 | reason | 조건 |
|---|---|---|
| 1 | `TARGET_UNREACHABLE` | 화재에서 가장 가까운 도로 노드가 `UGV_TARGET_SNAP_M` 보다 멂 |
| 2 | `BUSY` | 다른 task 주행 중 |
| 2 | `FAILSAFE_ACTIVE` / `COMMUNICATION_FAILURE` | 자원이 `UNAVAILABLE` (아래 주행 감시). `detail` 에 이상 내용 |
| 3 | `ROAD_BLOCKED` | 경로가 차단 도로 때문에 끊김. `detail` 에 원인 도로 id |
| 4 | `TARGET_UNREACHABLE` | 차단과 무관하게 도로망이 끊겨 있음 |

`UGV_APPROACH_FALLBACK=1` 이면 3·4 에서 바로 거절하지 않고, 화재에서 `UGV_APPROACH_MAX_M` 안의 다음 노드를 가까운 순으로 시도한다. 성공하면 `detail` 에 접근 거리를 적는다.

### 도로 위 지점에 서기 (`target_mode: "road_point"`, `ugv/road_point.py`)

교차로 사이 도로가 길면 노드 방식은 목표에서 먼 교차로에 선다. 도로 위 지점 방식은 목표 좌표를 가장 가까운 도로 선형에 투영한 점에 선다
(긴 도로 중간 계측용). evaluate·execute 에 `"target_mode": "road_point"` 를 주거나 서버를 `UGV_TARGET_MODE=road_point` 로 띄운다
(기본 `node` — 지금까지 동작 그대로. `cargo` 가 있거나 `target` 없이 `target_node` 만 주면 노드 방식.
총괄은 평가에서 받은 `target_node` 를 실행 때 `target` 과 같이 돌려보내는데, 이때는 `target` 기준으로 다시 골라 평가와 같은 지점에 선다).

1. 목표 좌표 → 가장 가까운 도로 위 점 (`TARGET_SNAP_M` 보다 멀면 `TARGET_UNREACHABLE`)
2. 그 도로 양 끝 노드 중 (그 노드까지 + 도로를 따라 지점까지) 시간이 짧은 쪽으로 들어간다. ETA 에 꼬리 구간이 들어간다
3. 응답의 `target_node` = 들어가는 끝 노드, 새 필드 `stop_point` = `{road_id, lat, lon, snap_m, along_m}` (실제로 설 곳). 노드 방식이면 `null`
4. 도착하면 차는 지점에 서 있고 `current_node` 는 들어온 끝 노드다. 다음 출발은 도로 중간 출발 규칙(양 끝 중 빠른 쪽)
5. 같은 지점(`NODE_ARRIVE_M` 20 m 안)으로 다시 보내면 움직이지 않고 바로 COMPLETED (`already_there`) — 붙박이 반복 관측
6. 지점이 있는 도로가 막혀 있으면 `ROAD_BLOCKED`. 주행 중 막히면 재탐색이 실패해 task FAILED(ROAD_BLOCKED)

경로(`/ugv/{id}/route` 의 `legs`, 실행 기록 `ROUTE`) 마지막에 꼬리 구간이 `to: null`, `to_point: {lat, lon}` 으로 붙는다.
보고(`UGV_TASK_STARTED`·`UGV_ARRIVED`)와 task 상태에 `stop_point` 가 실린다. 총괄은 이 필드를 몰라도 된다 (노드 방식과 같은 흐름).

ETA(시뮬레이션 초)는 도로마다 `길이 ÷ 차량 속도 × 혼잡 배율` 의 합이다. 도로 제한속도는 보지 않는다 — 막힘·혼잡만 차를 늦춘다.
차량 속도는 `ugv/config.py`: PX4 주행은 `max_speed_mps` (Gazebo r1_rover 2.0 m/s, A→B 29 km ≈ 4.1 h),
sim 드라이버 주행은 `sim_speed_mps` — 세 대 모두 19.4 m/s(약 70 km/h, A→B 약 25분). ETA 와 주행이 같은 값을 쓴다.
PX4 차량도 같은 구간 속도로 달린다 (미션 항목별 속도).

## POST /ugv/{resource_id}/execute

Safety ALLOW 이후 호출한다. 주행을 시작하고 즉시 반환한다.
UAV 와 같이 **화재 좌표(`target`)** 를 받는다. 목적지 도로 노드는 evaluate 와 같은 규칙으로 다시 고르므로, evaluate 이후 도로가 막혔으면 여기서 거절된다.

**요청** — `target` 과 `target_node` 중 하나

```json
{"task_id": "task-101", "decision_id": "dec-001", "target": {"lat": 38.0444, "lon": 128.2028}}
```

`target_node` 는 노드 id 를 직접 지정할 때만 쓴다 (시험·시연용).

**응답 200**

```json
{"task_id": "task-101", "resource_id": "A-ugv1", "status": "STARTED",
 "tracking_url": "/ugv/A-ugv1/task/task-101",
 "target_node": {"node_id": "494852", "lat": 38.043899, "lon": 128.202801, "snap_m": 55.6},
 "eta_sec": 436}
```

| 코드 | 의미 |
|---|---|
| 404 | 자원 또는 도로 노드 없음 |
| 409 | 다른 task 수행 중, 같은 task 진행 중, 또는 판단 결과 REJECT (`detail` 에 reason) |
| 422 | `target`·`target_node` 둘 다 없음 |
| 500 | 드라이버가 주행을 시작하지 못함 (PX4 arm·미션 거부 등) |

## POST /ugv/{resource_id}/stop

주행을 멈춘다. 진행 중 task 는 `CANCELLED`. `UNAVAILABLE` 자원을 `READY` 로 복귀시키는 방법이기도 하다. 멈춘 위치에서 가장 가까운 도로 노드에 선 것으로 보고 `READY` 로 돌린다. PX4: 미션 일시정지 → HOLD → disarm.

## GET /ugv/{resource_id}/task/{task_id}

| 필드 | 설명 |
|---|---|
| `status` | `STARTED` → `IN_PROGRESS` → `COMPLETED` / `FAILED` / `CANCELLED` |
| `progress` | `{"phase": "ENROUTE" \| "ARRIVED", "waypoint": i, "total": n}` |
| `observation` | COMPLETED 일 때 `{"observation_type": "ROAD_STATUS", "arrived_node", "position", "fuel_pct"}` |
| `error` | FAILED 일 때 |

도착은 도로 노드 도착이다. **화재를 관측했다는 뜻이 아니다.**

### 주행 감시 (watchdog)

주행 중 0.5 초마다 확인한다. 이상이 확정되면 task 는 `FAILED`(`error` = `CODE: 설명`), 차는 정지(HOLD), 자원은 `UNAVAILABLE` 이 된다.
**자동으로 READY 로 돌아오지 않는다** — 떨어지거나 고장 난 차가 곧바로 READY 가 되면 총괄이 다시 배정하므로, 운영자가 확인하고 `POST /stop` 으로 복귀시킨다.

| CODE | 조건 (기본값, `ugv/config.py`) | evaluate reason |
|---|---|---|
| `STALLED` | `STALL_TIMEOUT_S`(60 s) 동안 `STALL_MOVE_M`(10 m) 도 못 움직이고 웨이포인트도 그대로 | `FAILSAFE_ACTIVE` |
| `OFF_ROUTE` | 경로(노드를 이은 선)에서 `OFF_ROUTE_M`(100 m) 넘게 벗어남 | `FAILSAFE_ACTIVE` |
| `VEHICLE_FAULT` | PX4: 하강 속도 > `FALL_RATE_MPS`(8 m/s, 추락 — 지형 월드라 고도 자체로는 판정하지 않는다), 미션 중 disarm, 미션 중 MISSION 모드 이탈 | `FAILSAFE_ACTIVE` |
| `TELEMETRY_LOST` | PX4: 위치 수신이 `STALE_AFTER_S`(10 s) 넘게 없음 | `COMMUNICATION_FAILURE` |

`VEHICLE_FAULT`·`TELEMETRY_LOST` 는 출발 후 `FAULT_GRACE_S`(5 s) 이후부터, `FAULT_CONFIRM_S`(3 s) 이상 계속될 때만 확정한다 (arm·모드 전환 중 순간 신호 무시).

## GET /ugv/{resource_id}/observation

주행하지 않고 현재 도로 상태를 돌려준다. 필드 이름은 공통 `Observation` 을 따른다 (`simulation_time_s` 는 호출측이 붙인다).

```json
{"resource_id": "A-ugv1", "location_lat": 38.09279, "location_lon": 128.179569,
 "observation_type": "ROAD_STATUS",
 "value": {"state": "READY", "current_node": "A", "current_task_id": null,
           "blocked_roads": 5, "blocked_nodes": 1}}
```

## 도로 환경 API (`/roads/*`)

도로 환경은 UGV 것이고 환경 모듈(화재)과 별개다. 차단은 출처별로 기록되어 서로 풀지 않는다:
`scenario`(시나리오 파일), `manual`(API 직접), `cells`(구역 통제), 노드 차단은 `<출처>-node:<노드id>`.

| 호출 | 본문 | 비고 |
|---|---|---|
| `POST /roads/{road_id}/block` | `{"blocked": true}` | false 로 해제. 시나리오가 같은 도로를 막고 있으면 그대로 막혀 있다 |
| `POST /roads/nodes/{node_id}/block` | `{"blocked": true}` | 응답 `roads` 에 함께 막힌 도로 id |
| `POST /roads/closures/cells` | `{"cells": [{"x": 134, "y": 123}], "margin": 1}` | 매 호출이 전체 목록(스냅샷). 빈 목록이면 해제. 칸·이웃 margin 칸을 지나는 도로 차단 |
| `GET /roads` | | `blocked`, `blocked_by`, `blocked_nodes`, `congested` |

주행 중인 차량은 남은 경로가 막히면 재탐색한다 (아래 "주행 중 도로 차단").

## POST /roads/congestion

혼잡 직접 설정. 시나리오 혼잡 시간대가 켜진 도로는 다음 갱신(1초) 때 시나리오 값으로 다시 덮인다.

| 필드 | 기본 | 설명 |
|---|---|---|
| `preset` | `none` | `none`: 전부 1.0 / `random`: 시드 고정 랜덤 |
| `seed` | 0 | 같은 seed 면 같은 결과 |
| `ratio` | 0.2 | random: 혼잡 도로 비율 |
| `min_factor` / `max_factor` | 1.5 / 3.0 | random: 통과시간 배율 범위 |
| `roads` | null | `{road_id: 배율}` 직접 지정 (preset 적용 후 덮어씀) |

## 공통 커넥터 대응 (`connectors/ugv_connector.py`, real 모드)

루트 `config.py` 에서 `UGV_CONNECTION_MODE = "real"`, `UGV_SERVER_URL = "http://localhost:8100"`.

| 커넥터 함수 | 서버 호출 | 반환 |
|---|---|---|
| `get_ugv_status(base)` | `GET /ugv?base=` | `ResourceStatus` 목록. 서버 연결 실패 시 빈 목록 |
| `send_ugv_command(task_id, assignment)` | `POST /evaluate` (좌표) | `LocalResponse`. ETA·목적지 노드는 `counter_constraint` 에 임시로 실음 (공통 형식에 칸이 생기면 이동) |
| `get_ugv_observation(resource_id, ts, task_id, ...)` | ACCEPT 된 task: `POST /execute`(evaluate 때의 좌표) → `GET /task` 폴링 / 그 외: `GET /observation` | `Observation` (`ROAD_STATUS`) |

## 알려진 제한

- sim 주행 속도는 시연용 가속값(2,000 m/s). ETA 는 실제 도로 속도 기준.
- 주행 중 도로가 막혀도 경로를 다시 짜지 않는다.
- task 기록은 메모리에만 있다. 서버를 재시작하면 사라진다.
- 도로등급별 속도, 2,000 m 스냅 거리, 거점 위치는 잠정값이다 (팀 합의 필요).


## 주행 중 도로 차단 (재탐색)

주행 감시(`_watch_task`)가 0.5초마다 남은 경로(지금 달리는 도로 제외)에 막힌 도로가 있는지 본다.

| 경우 | 동작 | task |
|---|---|---|
| 우회로 있음 | 지금 도로 끝 노드에서 재탐색, 새 경로로 미션 교체 | `IN_PROGRESS` 유지, `reroutes[]` 에 `{sim_time_s, result: REROUTED, blocked_road_id, eta_s}` |
| 우회로 없음 | 멈추고 가장 가까운 노드에서 `READY` (고장이 아니므로 `UNAVAILABLE` 아님) | `FAILED`, `error: "ROAD_BLOCKED: ..."` |

`progress` 에 `remaining_m`, `eta_remaining_sec`, `current_road_id`, `sim_time_s` 가 붙는다.

## 시나리오 파일 (도로 환경)

`ugv/scenarios/*.csv` 또는 `*.json` — 한 줄 = "이 대상은 start 부터 end 전까지 이렇다". 형식 상세는 `ugv/scenario.py` 머리말.

| 열 | 값 |
|---|---|
| `kind` | `road`(도로 차단) / `node`(경유 불가 노드) / `congestion`(혼잡 — 막히게 할 도로만) |
| `target` | road_id 또는 node_id. 여러 개는 `\|` 로 |
| `start`, `end` | 초(`600`) / 시:분(`00:10`) / 환경 스텝(`step:10`). end 비우면 끝까지 |
| `value` | congestion 배율 (2.0 = 통과시간 2배) |

예시 `inje_girin.csv` (`UGV_SCENARIO=ugv/scenarios/inje_girin.csv` 로 켤 때):

| 시간대 | 대상 | 내용 |
|---|---|---|
| 00:00–01:00 | 인제읍 시가지 7개 도로 | 혼잡 ×2.0 / ×1.5 |
| 00:05–00:15 | 노드 494915 | 내린천로 입구 교차로 경유 불가 (+21분 우회) |
| 00:10–01:30 | 도로 682500248 | 내린천로 낙석 (+46분) |
| 00:20–02:00 | 도로 683400091 | 내린천로 기린 쪽 공사 (겹치면 +93분) |
| 01:00–03:00 | 도로 683400513 | 대내로 기린 진입 혼잡 ×3.0 |

규칙은 매 갱신마다 "지금 켜져 있어야 할 것"을 다시 계산한다. 시계가 되돌아가도(환경 새 실행, `/scenario/reset`) 그 시각에 맞게 다시 걸린다.
갱신 간격은 벽시계 1초라 시뮬레이션 기준으로는 `UGV_TIME_SCALE` 초 단위로 반영된다 (500배속이면 약 500초 늦을 수 있다).


## 총괄 보고 (push, `ugv/reporter.py`) — 기본 꺼짐

총괄이 1초마다 조회(polling)하므로 기본으로는 보내지 않는다. 필요해지면 `UGV_REPORT_URL` 만 주면 된다.

UGV 자원도 UAV 처럼 총괄이 개별로 지휘한다 (현장 지휘 역할 없음). 우리는 평가·수행하고 일이 생길 때마다 보고한다.
기존 조회 경로(총괄이 1초마다 `GET /ugv/{id}/task/{task_id}`)는 그대로 두고 그 위에 더한다.

형식 — 총괄 `POST /events` 그대로: `{"event_id", "type", "payload"}`.
`event_id` 는 서버 기동 시각 + 순번이라 재시도해도 총괄이 중복으로 처리한다.
`simulation_time_s` 는 보내지 않는다 (UGV 시계와 총괄 시계가 아직 안 묶여 있어 총괄이 미래 시각으로 거절할 수 있음). 우리 시각은 `payload.sim_time_s`.

| type | 언제 | payload 주요 필드 (공통: resource_id, task_id, sim_time_s, state, position, fuel_pct) |
|---|---|---|
| `UGV_EVALUATED` | evaluate 응답 | decision_id, verdict, eta_sec, reason, detail, target_node |
| `UGV_TASK_STARTED` | execute 로 출발 | decision_id, target_node, eta_sec, path |
| `UGV_PROGRESS` | 달리는 도로가 바뀔 때 | waypoint, total, remaining_m, eta_remaining_sec, current_road_id |
| `UGV_REROUTED` | 주행 중 차단으로 경로 변경 | blocked_road_id, eta_remaining_sec, reroutes |
| `UGV_ARRIVED` | 목적지 도착 | target_node, observation(ROAD_STATUS), reroutes |
| `UGV_TASK_FAILED` | 차단·우회 불가 / 차량 이상 / 내부 오류 | reason(ROAD_BLOCKED·STALLED·OFF_ROUTE·VEHICLE_FAULT·TELEMETRY_LOST·INTERNAL_ERROR), error |
| `UGV_TASK_CANCELLED` | /stop | reason |
| `RESOURCE_CHANGED` | 도착·실패·중지·이상 해제로 자원 상태가 바뀜 | why, current_node, fault — **총괄이 보류 임무를 다시 배정하는 계기** |

총괄 쪽 처리: `RESOURCE_CHANGED` 는 재배정, `UGV_*` 는 현재 장부(`EXTERNAL_EVENT`)에 기록만 된다.
보고 실패는 주행에 영향 없다 (3회 재시도 후 버리고 로그). A→B 29 km 한 번에 진행 보고가 약 70~90건 나온다.

## 도로 상황판 (`GET /view`, `ugv/static/road_view.html`)

UGV 서버가 직접 내주는 화면. 이 서버 API 만 폴링하고 총괄·관제판과는 무관하다 (`http://<UGV 서버>:8100/view`).

| 영역 | 내용 |
|---|---|
| 보기 | 상단 **지도 / 그래프** 전환. 지도 = 환경 격자 지형(LIVE 화면과 같은 고도·연료 자료, 언덕 음영) 위 실제 도로 선형. 그래프 = 교차로 사이 도로를 한 간선(직선)으로 묶은 단순 그래프, 노드를 크게 — 알고리즘 설명용 |
| 지도 | 도로망 전체. 차단 = 빨간 점선, 혼잡 = 주황(배율이 클수록 굵게), 경유 불가 노드 = 빨간 원. 도로에 마우스를 올리면 이름·차단 출처·혼잡 배율. 교차로 노드는 늘 보이고, 길이 휘는 점은 확대(14 이상)하면 보인다 |
| 차량 | 소방차·UGV 모양 아이콘. 같은 자리에 겹치면 둘레로 벌려 둘 다 보인다. 위치 보고 사이(실시간 1초 조회, 재생은 약 50 시뮬레이션 초 간격)는 달리는 경로의 도로 모양을 따라 메워 움직인다 — 고속(소방차)에서도 끊기거나 산길을 가로지르지 않게. 목록에 지금 임무·자리(노드 / 도로 A→B)·목적지·남은 시간·경과·작전 이유 |
| 도로 표시 | 마우스를 올리면 도로명·혼잡 배율·교통 상황(기준속도 대비 80% 이상 원활 / 50% 이상 서행 / 그 밑 정체 / 통제)·차단 출처. 상단에 통제·서행/정체 도로 수 |
| 직접 명령 | 차를 고른 채 노드를 누르면 그 차의 현재 임무(목적지·남은 시간·작전 이유)를 보여 주고 "바꾸시겠습니까?" → 바꾸기 = 정지 후 평가·출발. 총괄이 맡긴 임무를 바꾸면 그 임무는 FAILED(OPERATOR_OVERRIDE) 로 닫혀 총괄이 인계한다 |
| 출동 | 노드를 누르면 `UGV 출동 요청` / `소방차 출동 요청` → 총괄에 그 지점까지 **이동 임무**(sensor 없음, 도착으로 완료)를 요청. 어느 차가 갈지·Safety 는 총괄이 정한다. 실시간에서만 |
| 도로 위 지점 | (지도 보기) 도로를 누르면 그 도로 위 점에 대해 같은 메뉴 — 차를 골랐으면 그 차를 지점에 세우는 직접 명령, 아니면 총괄 출동 요청(총괄은 90 m 칸 중심으로 보내므로 지점에 서는 건 `UGV_TARGET_MODE=road_point` 일 때). 경로 끝 꼬리 구간과 `도착(도로 위)` 라벨, 차량 목록 `○○ 위 지점에 정차` |
| 차량 | 상태·진행·남은 시간·재탐색 횟수. 누르면 그 차만 강조하고 경로·구간 소요시간 라벨을 지도에 그린다 |
| 경로 표 | 이름이 같은 도로 구간을 한 줄로 묶어 거리·소요시간(지금 혼잡 기준)·혼잡. 지나온/달리는/남은 구간 구분. 줄에 올리면 지도에서 강조 |
| 기록 | 출동 하나를 한 묶음(▶)으로 — 대표 줄에 task_id·출처·ETA(재탐색 시 바뀐 ETA)·경과 시간·상태(진행/도착/중단/변경/실패). 누르면 펼쳐 평가·출발·재탐색·도착을 본다. 그 밖에 실행 기록 시각순 — 평가·출동·재탐색·도착·실패·도로 상황 변화(무엇이 막히고 풀렸는지·켜진 시나리오 규칙). 누르면 관련 도로·위치를 지도에 강조 |
| 도로 상황 | 켜진 시나리오 규칙·예정 규칙, 막힌 도로·노드·혼잡 개수. 시나리오가 아닌 출처(API 직접 = 수동 통제, 격자 칸 = 구역 통제)로 막힌 도로는 "규칙 밖 통제"로 따로 |
| 과거 실행 | 상단 목록에서 지난 실행을 고르면 기록 전체로 그 시각의 상태(차량 위치·경로·도로 상태)를 다시 만든다. 시간 막대·재생(10~1200배), 막대의 눈금 = 출동·재탐색·실패·도로 변화 |

실행 기록 (`ugv/history.py`): 서버 한 번 기동 = 실행 하나. 총괄 보고와 같은 이벤트에 더해 `RUN_START`(자원·시나리오),
`ROAD_STATE`(바뀔 때만), `ROUTE`(출발·재탐색 때 경로와 구간 소요시간)를 적는다. 화면 전용이며 총괄로 보내지 않는다.
지도 라이브러리(Leaflet)는 CDN 에서 받으므로 화면을 여는 브라우저는 인터넷이 필요하다. 배경 지도(OSM)는 `배경` 버튼으로 켠다.

상황판 출동이 sensor 없는 이동 임무인 이유 (2026-10-08 확인): `WEATHER` 는 총괄이 목표 칸이 화재·위험 칸 목록에 있을 때만
'목표 달성'으로 쳐서 임의 도로 노드로는 도착·측정·재출동이 반복되고, `ROAD_STATUS` 는 총괄 능력표에 소방차가 없어 후보에서 빠진다.
