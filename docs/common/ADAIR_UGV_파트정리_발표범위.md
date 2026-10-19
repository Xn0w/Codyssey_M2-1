# UGV 파트 정리 — 발표용

> **한눈에 보기**
> - UGV는 총괄의 **수행 가능성 평가(evaluate)** 요청에 도로로 갈 수 있는지와 걸리는 시간(ETA)을 답하고, **실행(execute)** 요청을 받으면 도로를 따라 가서 도착 위치를 보고합니다.
> - 길은 **Dijkstra 알고리즘**으로, 거리가 아니라 **가장 빨리 가는 길**을 찾습니다.
> - 처음엔 **Gazebo(PX4)** 로 달렸지만 시연 배속 100을 따라가지 못해, 통합은 **sim(UGV 서버가 직접 위치 계산)** 으로 했습니다 ([0장 참조](#0-sim으로-결정한-이유)).
> - 팀 시연과 같은 조건(2019 인제 트윈, 배속 100)에서 **4대가 총괄 요청으로 26번 출동해 모두 도착**했습니다 (2026-10-11).
> - 갈 수 없는 목표(도로에서 2 km 넘게 먼 산속)를 주면 **`TARGET_UNREACHABLE`로 거절**하고 총괄은 보류합니다 — 통합 환경과 팀 main 총괄 모두에서 확인했습니다.
> - 발표에서는 도로 상황판의 **다시 보기**로 출동 → 경로 → 주행 → 도착 과정을 보여 줍니다.
> - 테스트가 총괄담당 하신 수진님의 레포지토리(https://github.com/sujinpark50-gif/ADAIR)가 통합될 것으로 전제하고, 해당 버전의 오케스트레이터 디렉토리와 환경 모듈을 이용하여 이루어졌습니다. 시연 시나리오에서는 ugv,소방차는 출동이 적습니다. 설명중 통합환경은 이를 의미합니다. run_servers.py start --twin 실행시 소방차의 출동을  , bash ugv/tools/run_twin_ugv.sh thermal 실행 시 ugv출동을, 확인하실 수 있습니다. 발표에서 시연이 필요하면 로컬에서 해당 건들만이나 도로현황판에서 실행해도 될 것 같습니다.

| 항목 | 내용 |
|---|---|
| 담당 | UGV (지상 자원 — 무인 지상 차량·소방차) |
| 시험 기간 | 2026-10-10 ~ 10-11 (시험 목록 5장. 배속 측정은 0장). 로컬 = macOS, Gazebo = Windows WSL |
| 발표 범위 | UAV·UGV가 환경 모델의 화재를 관측하고, 총괄이 모아 인지 지도를 만드는 과정 (진화·살수 제외) |
| 자료 | 근거 [`docs/ugv/evidence/`](../ugv/evidence/) · 영상 [`docs/ugv/media/`](../ugv/media/) · 상세 [`ugv/README.md`](../../ugv/README.md) |

---

## 0. sim으로 결정한 이유

처음에는 PX4가 제공하는 차량 모델 r1_rover(최고 2 m/s, 시속 7 km)로 Gazebo에서 달렸습니다. 경로를 PX4 미션으로 보내 도로를 따라 도착했고 ETA도 맞았습니다(실제/예상 1.01~1.05). 실제 차처럼 보이려면 Gazebo를 빠르게 돌려야 해서, 화면(GUI)을 켜고 4배까지 시험한 뒤 화면을 끄고 배속을 따로 쟀습니다.

| 날짜 | 환경 | 요청 배속 | 실제 배속 |
|---|---|---|---|
| 10/3 | Windows WSL, 화면 끔, PX4 기본 빈 월드 | 10 | 3.5 ~ 4.2 |
| 10/3 | Windows WSL, 화면 끔, 도로를 배치한 월드 | 4 | 3.77 |
| 10/5·10/11 | Windows WSL, **화면 켬**, 도로를 배치한 월드 | 4 | **3.2** |
| 10/5–10/6 | Windows WSL, 화면 끔, 도로를 배치한 월드 | 10 | 중앙값 6.3 (순간 0.5–2까지 떨어짐) |
| 10/11 | 로컬, 화면 끔, 도로를 배치한 월드 (참고) | 10 | 9.99 (주행 성공) |
| 10/11 | 로컬, 화면 끔, 도로를 배치한 월드 (참고) | 30 | PX4 시동 점검 실패 |

개발과정에서 팀 시연은 배속 100인데 어느 환경도 10을 넘지 못했습니다. 그래서 **통합은 sim**(UGV 서버가 도로 선형을 따라 시속 60 km로 위치를 계산)으로 하고, **Gazebo는 "실제 차량 모델로도 같은 경로·ETA로 달린다"는 단독 근거**로만 씁니다. Gazebo를 통합하려면 Gazebo를 따로 느리게 돌리는 게 아니라 차량 모델 속도를 올려 시연 배속에 맞춰야 합니다 (발표 이후 과제, [8장](#8-가정과-한계)).

![Gazebo 1대 + 도로 상황판 직접 지시 + 3D 트윈 LIVE + QGroundControl (10/11, 배속 약 3.2)](../ugv/media/ugv_gazebo_live_1011.gif)

---

## 1. 역할

```
총괄 ── 수행 가능성 평가 (evaluate) ──▶ UGV ── ACCEPT(ETA·경로) / REJECT(사유)
총괄 ── 실행 (execute) ─────────────▶ UGV ── 도로를 따라 주행 → 도착
총괄 ◀── 진행 조회 (task) ─────────── UGV
UGV  ── 시뮬레이션 시각 (/health) ──▶ 환경 모듈
```

| UGV가 맡는 것 | UGV가 맡지 않는 것 |
|---|---|
| 수행 가능성 평가: ACCEPT(ETA·경로) / REJECT(사유) | 어느 차를 어디로 보낼지 → **총괄** |
| 도로를 따라 주행, 위치·진행 보고 | 열화상 관측값 계산 → **총괄 모의 센서** |
| 도로 통제·혼잡 반영, 막히면 우회 | 화재 확산 → **환경 모듈** |
| 판단·주행·이상을 시각과 함께 기록 | |

UGV 서버 하나(포트 8100)가 차량 4대(인제119·기린119에 UGV 1대, 소방차 1대씩)를 맡습니다. 도로망은 강원 인제 실제 도로 자료(노드 664개, 도로 820개)입니다. 노드 = 교차로와 도로 끝점.

![Gazebo의 소방차 모델 (r1_rover 기반)](../../ugv/ugv_image/gazebo_rover_firetruck.png)

> **발표 시 주의사항:** "UGV가 열화상으로 불을 찾았다" ✗ → "UGV가 관측 위치까지 도로로 가서 위치를 보고했고, 총괄의 모의 센서가 그 위치에서 관측값을 만들었다" ✓

---

## 2. 구현한 것 / 안 한 것

**실행까지 확인한 기능**

| 기능 | 어디서 확인 |
|---|---|
| 상태 조회 (위치·상태·지금 도로·임무·시각) | sim, PX4 |
| 수행 가능성 평가 — ACCEPT(최단 시간 경로, ETA) / REJECT(사유) | 단독 재현, 거절은 통합 환경·팀 저장소 트윈에서도 (5-3 ④) |
| 도로를 따라 주행 → 도착 | sim 4대, PX4/Gazebo 1대 |
| 주행 중 앞길이 막히면 우회 | UGV 단독 재현 |
| 같은 요청이 두 번 와도 한 번만 출발 / 정지하면 임무 취소 | UGV 단독 재현 |
| 주행 이상 감지 (멈춤·경로 이탈·차량 이상) → 사용 불능(UNAVAILABLE) | PX4/Gazebo |
| 환경 모듈 시계 따라가기 ([4장 시각 기준](#4-입력과-출력-api)) | 팀 저장소 트윈+통합 환경 |
| 도로 상황판 (`/view`): 차량·경로·막힌 도로 표시, 실행 기록 다시 보기 (화면에 "AI 생성 화면" 상시 표시) | 모든 환경 |
| 도로 상황판에서 직접 지시 (차를 골라 노드·지점으로 출동, 운영자 예외) | 모든 환경 |
| **총괄과 연동, 4대 동시 운용** | **통합 환경 (배속 100)** |

**미완성·미통합 기능 (기본 꺼짐)**

| 기능 | 켜는 법 | 구현 범위 | 미완성·미통합 사유 |
|---|---|---|---|
| 소방차 방수 | `UGV_SUPPRESSION=1` | **부분 구현** — 물탱크·펌프 상태 모델(Python)과 Gazebo 물줄기 표시(플러그인)까지. 기능 작동은 확인 | 환경 모듈과의 상호작용(불을 끄는 효과) 미구현. 발표 범위(진화 제외) 밖 |
| 짐 싣기·운반 | — | 적재 한도·싣는 곳 경유 코드만 | 총괄이 짐을 보내지 않음 |

도로 판단 AI(막힌 도로 앞에서 우회·대기 결정)는 이 PR에 없고 별도 PR(`feat/ugv-road-ai`)에서 다룹니다.

**하지 않은 것 (발표 이후 과제)**
- UGV 자체 센서 측정 (지금은 총괄 모의 센서가 대신함)
- 배터리로 판단·복귀 — 지금은 표시용이라 배터리가 0 %가 되어도 거절하거나 멈추지 않음
- Gazebo 차량을 시연 배속 100·시속 60 km로 (지금 차량 모델은 2 m/s)
- 사용 불능(UNAVAILABLE) 자동 해제 (지금은 수동으로 요청 — Swagger에서 `POST /ugv/{id}/stop`, 또는 도로 상황판에서 그 차에 직접 지시)

---

## 3. 어떻게 판단하나

### 3-1. 수행 가능성 평가(evaluate)의 순서

| 순서 | 확인 | 안 되면 |
|---|---|---|
| ① | 목표까지 거리 재기: 가장 가까운 도로 노드가 **2 km 안**인가 | 거절 `TARGET_UNREACHABLE` |
| ② | 차가 사용 불능(UNAVAILABLE)인가 | 거절 `FAILSAFE_ACTIVE` / `COMMUNICATION_FAILURE` |
| ③ | 다른 임무 중인가 | 거절 `BUSY` |
| ④ | 길이 있나 (Dijkstra) | 다 막힘 `ROAD_BLOCKED` / 안 이어짐 `TARGET_UNREACHABLE` |
| ⑤ | 모두 통과 | **수락** + ETA + 경로 |

평가만 하고 **차는 움직이지 않습니다.**

**①의 거리 재기는 수선의 발로 합니다.** 목표 T에서 도로 선형의 각 구간 A–B에 수선을 내려 발 P를 구하고, 가장 짧은 것을 고릅니다. 설 자리를 고르는 방식은 두 가지입니다.

- **road_point (기본, 10/11부터):** 수선의 발 **P(도로 중간)**에 섭니다. 노드 사이가 길 때 목표에 더 가까이 섭니다. |T−P|가 2 km를 넘으면 거절. 오케스트레이터 요청은 `target_mode`를 보내지 않으므로 기본값인 이 방식을 씁니다
- **node:** 목표에서 가장 가까운 **노드**에 섭니다. 노드까지 2 km가 넘으면 거절. 10/11 이전 기본값이라 5-3의 ①~④는 이 방식이고, ⑤는 `road_point`입니다

**총괄의 UGV 열화상은 반경 600 m 상시 + 2 km 지형 시선이고(팀 main, 10/12), UGV 수락 거리 2 km와 같습니다.** UGV는 도로 위 점에 서서 목표에 더 가까이 갑니다 (기본값 `road_point`).

![수선의 발: 목표 T에서 도로 구간에 수직으로 내린 점 P. node 방식은 가장 가까운 노드 N1·N2 중 하나](../../ugv/ugv_image/road_point_foot.svg)

```
P = A + t·(B − A),   t = (T − A)·(B − A) / |B − A|²   (0보다 작으면 0, 1보다 크면 1 → 구간 끝점)
snap_m  = |T − P|                         목표에서 설 자리까지 직선거리
along_m = 도로 시작 노드 → P 를 도로를 따라 잰 거리   (ugv/road_point.py)
```

### 3-2. 비용 = 지나가는 데 걸리는 시간
점과 선의 연결을 수학에서 그래프라고 합니다.
이 때 선을 지나서 다른 점으로 이동하는 방법을 경로라고 합니다. 그 때 누적 되어가는 양들을 비용이라고 할 수 있습니다.
실제 자동차가 한지점에서 도로를 통해서 이동하는 것은 이 그래프에서 한지점에서 다른 지점으로 이동하는 경로로 나타낼 수 잇습니다. 
현실에서 교통비, 이동시간, 이동거리 도이 이 비용이라고 할 수 있습니다.
ugv에서는 빠른 도착을 위해 시간을 비용으로 삼고 가장 적은 비용으로 이동하는 방법을 빨리 찾을 수 있는 디익스트라 알고리즘을 이용 하였습니다.
```
도로 하나의 비용(초) = 도로 길이 ÷ 속도 × 혼잡 배율
  속도 = min(도로의 주행가능 속도(최저 50 km/h), 차량 최고속도 60 km/h) //자동차의 최고속도와 도로의 주행가능 속도 중 작은 것을릅따름니다. 도로망 정보에서 국도·고속국도는 60km/h, 시군도·기타는 50km/h로 정했습니다.build_road_network.py 참고 
통제된 도로 = 비용 무한대  →  경로에서 저절로 빠짐
ETA = 경로에 있는 도로 비용의 합
```

같은 거리라도 느린 도로·혼잡한 도로는 비용이 큽니다. 그래서 **가까운 길이 아니라 빠른 길**을 찾습니다.

### 3-3. Dijkstra 알고리즘

![Dijkstra 단계별 예시](../../ugv/ugv_image/dijkstra.gif)

- 선 위 숫자: 그 도로를 지나는 데 걸리는 시간(분)
- 점 아래 숫자: 출발점 A에서 그 점까지 지금까지 아는 가장 짧은 시간
- 색: 초록 = 확정 · 주황 = 지금 확정 · 파랑 = 후보 · 회색 = 아직 모름(∞)

**규칙: 처음에는 모든 다른 점으로 가는 비용을 무한이라 가정하고 시작점에서 부터 이웃 점들로 이동하는 비용들을 파악하면서 한 단계마다 내가 알고 있는 여태까지 최저 비용 경로가 확정되지 않은 모든 점들 중 가장 적은 비용으로 갈 수 있는 점은 최저 비용의 경로로 확신할 수 있다. 최저 비용 경로가 추가되면 그 도착점부터 이어서 이웃 점들에 가는 경로의 비용을 구한다. 또 여태까지 알고있는 모든 확정되지 않은 경로중에서 가장 짧은 경로를 그 경로의 종착점으로 가는 최저비용 경로로 확정한다. 원하는 점에 도달할 때까지 이 과정을 반복하면 출발점에서 원하는 점으로 가는 가장적은 비용의 경로를 알 수 있습니다.**

| 단계 | 확정 | A | B | C | D | E | F |
|---|---|---|---|---|---|---|---|
| 시작 | — | 0 | ∞ | ∞ | ∞ | ∞ | ∞ |
| 1 | A | **0** | 4 (A) | 2 (A) | ∞ | ∞ | ∞ |
| 2 | C | **0** | 3 (C) | **2** | 10 (C) | 12 (C) | ∞ |
| 3 | B | **0** | **3** | **2** | 8 (B) | 12 (C) | ∞ |
| 4 | D | **0** | **3** | **2** | **8** | 10 (D) | 14 (D) |
| 5 | E | **0** | **3** | **2** | **8** | **10** | 13 (E) |
| 6 | F | **0** | **3** | **2** | **8** | **10** | **13** |

숫자 = 지금까지 아는 가장 짧은 시간, 괄호 = 어디를 거쳐 왔나, 굵게 = 확정

- **결과:** A → C → B → D → E → F, 13분
- **눈여겨볼 곳:** B는 A에서 바로 가면 4분, C를 거치면 3분 → 가까워 보이는 길이 빠른 길은 아님
- **왜 가장 짧은 후보부터 확정해도 되나:** 다른 후보를 거쳐 오면 그 후보까지 이미 더 오래 걸렸고, 걸리는 시간은 음수가 될 수 없으니 더 짧아질 수 없습니다
- 실제 코드는 가장 짧은 후보를 빨리 꺼내려고 우선순위 큐(힙)를 씁니다 (`ugv/road_graph.py`)

### 3-4. 달리는 중에는

| 상황 | UGV가 하는 일 |
|---|---|
| 0.5초마다 | 남은 거리·시간·지금 도로를 기록 |
| 앞길에 통제가 생김 | 지금 위치에서 Dijkstra 다시 → **우회** |
| 다른 길이 없음 | 가까운 노드에 서고 임무 실패 (`ROAD_BLOCKED`), 차는 정상 |
| 60초 동안 10 m 못 감 / 경로에서 100 m 벗어남 / 차량 이상(시동 꺼짐·모드 이탈·위치 수신 끊김) | 임무 실패, 차는 사용 불능(UNAVAILABLE). 정지 명령으로 해제 |

## 4. 입력과 출력 (API)

전체 사양 `ugv/API_DEFINE.md`, 필드 설명 `ugv/README.md` 3장

| 요청 | 하는 일 |
|---|---|
| `GET /ugv` | 전체 차량 상태 |
| `POST /ugv/{id}/evaluate` | **수행 가능성 평가** — ACCEPT / REJECT (주행 안 함) |
| `POST /ugv/{id}/execute` | **실행** — 바로 `STARTED`, 주행은 뒤에서 |
| `GET /ugv/{id}/task/{task_id}` | 어디쯤인지, 도착 위치 |
| `POST /ugv/{id}/stop` | 정지 (임무 취소) |
| `GET /ugv/{id}/route` | 지금 경로와 남은 거리·시간 |
| `GET /health` | 서버 상태 |
| `POST /roads/{road_id}/block` | 도로 통제 (시험용) |
| `GET /view` | 도로 상황판 |
| `GET /history/runs/{run_id}` | 지난 실행 기록 |

**보내는 것** (evaluate, execute 같음)
```json
{"task_id": "T1", "decision_id": "D1",
 "target": {"lat": 38.02845, "lon": 128.1309}}
```

**받는 것** (실제 결과, 2026-10-11)
```json
{"verdict": "ACCEPT", "eta_sec": 344,
 "target_node": {"node_id": "494959", "snap_m": 40.7},
 "path": ["A", "495012", "…"]}
```
→ ACCEPT, 344초 걸림, 목표에서 40.7 m 떨어진 노드 494959에 섬. 이어서 실행하면 실제 348.9초에 도착 (5-3 ①, [영상 02](https://drive.google.com/file/d/1bw5k8rbyBo672su-RLFyA5ibGpZNnINr/view): Swagger 평가 → 실행 → 도착)

![Swagger 평가 → 수락](../../ugv/ugv_image/swagger_evaluate_accept.png)

![같은 임무를 도로 상황판에서 본 모습: A-ugv1 주행 중, 남은 4.9 km / 5분](../../ugv/ugv_image/road_view_task_running.jpg)

**도착하면** (총괄은 이 위치로 관측값을 만듦)
```json
"observation": {"observation_type": "ROAD_STATUS", "arrived_node": "494959",
  "position": {"lat": 38.028786, "lon": 128.130717}}
```

| 기준 | 값 |
|---|---|
| 좌표 | 위도·경도 (WGS84 — GPS가 쓰는 세계 공통 좌표계. 환경 모듈·드론과 같은 기준) |
| 시각 | 시뮬레이션 초. UGV는 1초마다 환경 모듈 `/health`의 시각을 읽어 자기 시계를 맞추고, 환경이 10초 넘게 응답하지 않으면 마지막 시각부터 혼자 흘림 (`UGV_TIME_SCALE` 배속). ETA·기록·도로 통제 시각이 모두 이 시계 기준 |
| 단위 | m, s, 속도는 설정에서 km/h |
| 임무 상태 | STARTED → IN_PROGRESS → COMPLETED / FAILED / CANCELLED |
| 차량 상태 | READY / RUNNING / UNAVAILABLE |

---

## 5. 테스트 (제작 과정에서 해 본 것)

### 5-1. 시험 환경

| 환경 | 구성 | 시험 |
|---|---|---|
| **UGV 단독** | 팀 저장소의 UGV 서버·모듈만. 총괄·환경 없음 (macOS) | ① |
| **Gazebo** | 팀 저장소, PX4 SITL + Gazebo(r1_rover) + UGV 서버(`UGV_DRIVER=px4`). 도로 상황판에서 직접 지시 (Windows WSL) | ② |
| **통합 환경** | 총괄 담당 수진님의 저장소([ADAIR](https://github.com/sujinpark50-gif/ADAIR) `feat/orchestrator-final` @ `221a497`, 10/8) **전체**에 우리 `ugv/` 폴더만 넣어 돌린 환경 (macOS). 총괄에 관측 계획(출동 전 확인 PROBE·불 따라가기)이 있고, 환경은 불이 번져 UGV를 계속 부릅니다. **팀 저장소만으로는 같은 결과가 나오지 않습니다** (아래 재현 방법) | ③④ (④는 팀 저장소 트윈에서도) |
| **팀 저장소 트윈** | 팀 저장소 그대로 `run_servers.py start --twin` 계열 (`ugv/tools/run_twin_ugv.sh` 구성). 관측 계획이 없고 트윈의 불이 첫 칸에서 꺼져, 따로 요청하지 않으면 UGV가 거의 불리지 않습니다 (macOS) | ④⑤ |

**통합 환경이 팀 저장소와 다른 곳** (`221a497` 기준, `ugv/`·`docs/` 제외)

| 위치 | 무엇이 다른가 |
|---|---|
| `orchestrator/` | 관측 계획(PROBE·불 따라가기). UGV 출동 횟수를 정함 |
| `environment/`, `web/static/inje2019/scenario.json` | 불 확산 설정. 불이 번져 UGV가 계속 불림 |
| `run_servers.py`, `tools/` (`twin_clock.py`, `twin_operator.py` 등) | 트윈 실행 설정 (신고 시점, 순찰 요청. 총괄 AI가 생각하는 동안 시계 멈춤은 개인 저장소 ADAIR에만 있음) |
| `config.py`, `uav/uav-agent/config.py` | 거점·드론 설정 |
| `.env` | 총괄 AI 모델 (로컬에서만 copa `claude-sonnet-4`, 팀 기본은 `gpt-5.5`) |

**통합 환경 재현 방법** — 팀 저장소에서 총괄·환경만 바꾸는 것이 아니라, 수진님 저장소의 `221a497`을 통째로 받아 `ugv/` 폴더만 이 저장소 것으로 바꿔 넣습니다. 웹 관제판은 팀 저장소 것을 함께 썼습니다. 그 저장소는 이후(10/10) UGV를 다시 구현했으므로 반드시 커밋 `221a497`로 맞춥니다. 우리 UGV 코드는 그때부터 주행·평가가 크게 바뀌지 않아, 이렇게 맞추면 같은 시험을 다시 돌릴 수 있습니다.

```bash
git clone https://github.com/sujinpark50-gif/ADAIR.git adair-221a497 && cd adair-221a497
git checkout 221a497
rm -rf ugv && cp -R <팀 저장소>/ugv ./ugv
bash ugv/tools/run_twin_ugv.sh dispatch
```

- ③④의 UGV 서버는 도로 AI 브랜치(`feat/ugv-road-ai`) 코드를 AI 끄고 돌렸습니다. 주행·평가 코드는 지금과 같습니다.
- Gazebo 배속 측정(macOS 10배 9.99, 30배 시동 실패 등)은 [0장](#0-sim으로-결정한-이유), 근거 [`2026-10-11_gazebo_speed`](../ugv/evidence/2026-10-11_gazebo_speed/).

### 5-2. 시연 시나리오와 구성

**팀 시연 시나리오 (2019 인제 트윈, `run_servers.py start --twin`)** — 2019-04-04 14:45 인제 남전리 산불을 환경 모델로 재현한 것입니다. 환경은 35분 단위(CA 한 단계)로 불을 계산하고(시계는 1분씩 진행하며 단계 사이를 채움), 신고는 발화 120초 뒤에 나며, 신고가 들어오면 총괄이 자동으로 초기 정찰(드론·UGV 허용)을 보냅니다. 드론 2대와 소방차가 총괄 요청으로 움직이고, 운용자 도구 2개(사람 대신 총괄 `/tasks`에 요청을 넣는 스크립트: `twin_operator.py`는 일몰 뒤 드론 순찰, `twin_ground_dispatch.py`는 불 확인 시 소방차의 남전1리 마을회관 방어 출동)가 함께 뜹니다. 배속 100, 도로 통제·혼잡 없음.

**네 구성** — 같은 트윈을 `bash ugv/tools/run_twin_ugv.sh <구성>` 한 줄로 켭니다. **모두 팀 저장소만으로 돌아갑니다.**

| 구성 | 무엇이 다른가 | 쓰인 곳 |
|---|---|---|
| `main` | UGV 열화상·지상 자동 정찰 끔(`ORCH_UGV_THERMAL=0 ORCH_AUTO_RECON_GROUND=0`) → UGV는 출동하지 않고 드론 순찰·소방차 방어만 | 비교용 |
| `dispatch` | 기본값 그대로 (신고 때 자동 정찰 후보에 UGV 포함, 10/9 팀 합의 `25a0183`). `run_servers.py start --twin`과 같음 | ③ (통합 환경에서 돌리셔야 합니다.) |
| `final` | `dispatch` + 거절 요청 1건 자동 (시뮬레이션 40분, 도로에서 2.2 km 넘게 먼 산속 칸으로 UGV 정찰 요청, `ugv/tools/twin_reject_request.py --auto`) | ④(소방차만 처음에 출동하고 ugv는 reject 합니다.) |
| `thermal` | 마을회관 방어 출동을 소방차 대신 UGV로 (`TWIN_DISPATCH_ARGS="--types UGV --site NAMJEON1_HALL,INJE_REST_AREA"`, 남전1리 마을회관·인제휴게소) + UGV 전용 열화상 요청 자동 (시뮬레이션 20분부터 30분마다 불 칸, 최대 6건, `ugv/tools/twin_thermal_request.py --auto`) | ⑤, 시연 ([7장](#7-발표에서-보여줄-동작)) |

거절 요청을 원하는 때에 손으로 넣으려면 `dispatch`로 켠 뒤 `.venv/bin/python ugv/tools/twin_reject_request.py`를 실행합니다.

### 5-3. 해 본 시험 (영상이 있는 것)

| # | 날짜 | 환경 | 시험 | 결과 | 근거 · 영상 |
|---|---|---|---|---|---|
| 1 | 10/11 | UGV 단독 | **Swagger** 수행 가능성 평가 → 실행 (배속 5) | ETA 344초 → 실제 348.9초 도착 (오차 1 %) | `2026-10-11_swagger`, [영상 02](https://drive.google.com/file/d/1bw5k8rbyBo672su-RLFyA5ibGpZNnINr/view) |
| 2 | 10/11 | Gazebo | 1대 직접 지시 2회 + 3D 트윈 LIVE·QGroundControl (화면 켬) | 모두 도착, 배속 3.26·3.23, ETA 대비 1.05, 경로 이탈 95 %가 0.76 m 이하 | `2026-10-11_gazebo`, [영상 07](https://drive.google.com/file/d/1FDUeMzhDdScPLViCn4qkAXgzBJ7bsy9N/view) |
| 3 | 10/11 | 통합 환경 | **일반 주행 4대** (`dispatch`), 총괄 요청 출동 | 출동 26회 모두 도착 (A-ugv1 13, B-ugv1 12, A-fire1 1) · 열화상 26회 중 14회 불 탐지 | `2026-10-11_twin4`, [영상 01](https://drive.google.com/file/d/1Ic2o8N6mWVAHP95pXV_fdyWmRf5ojPiC/view) |
| 4 | 10/11 | 통합 환경 + 팀 저장소 트윈 | **거절** (`final`): 도로에서 2.2 km 먼 산속 칸 20_57로 UGV 정찰 요청 | 두 환경 모두 A-ugv1·B-ugv1 `TARGET_UNREACHABLE` (노드까지 2201 m > 허용 2000 m) → 총괄 보류 `NO_FEASIBLE_CANDIDATE`, 출동 없음. 보류 뒤 재평가 반복 (통합 환경 138초에 27회, 팀 저장소 151초에 32회). 팀 저장소 쪽은 불이 일찍 꺼져 UGV 정찰 출동 0회, 소방차 1회 | `2026-10-11_final`, [영상 09](https://drive.google.com/file/d/1gaAT6Zct-FrcqPuWq4ibnaslTJCdRTlK/view) (팀 저장소 트윈) |
| 5 | 10/12 | 팀 저장소 트윈 | **`thermal`**: 마을회관·휴게소 방어 출동을 UGV로 + UGV 열화상 요청 | UGV 임무 3건 모두 완료 — 열화상 정찰(A-ugv1, 목표 80 m 앞 도로에 정차, 반경 2 km 안 321칸 보임·984칸 지형에 가림, 불 탐지), 마을회관(B-ugv1), 휴게소(두 대 모두 바빠 보류 2회 뒤 A-ugv1) | `2026-10-12_thermal`, [영상 10](https://drive.google.com/file/d/1SY68U-cmPt6lgy0qlqBAr5AMy7e0-hpU/view) |

- 근거 폴더: [`2026-10-11_swagger`](../ugv/evidence/2026-10-11_swagger/) · [`2026-10-11_gazebo`](../ugv/evidence/2026-10-11_gazebo/) · [`2026-10-11_twin4`](../ugv/evidence/2026-10-11_twin4/) · [`2026-10-11_final`](../ugv/evidence/2026-10-11_final/) · [`2026-10-12_thermal`](../ugv/evidence/2026-10-12_thermal/)
- 도로 상황판 다시 보기 기록(`history_*.jsonl`)과 총괄 기록(`orchestrator.sqlite3`)은 저장소에 올리지 않았습니다 (`.gitignore`, 용량).
- 통합 환경의 열화상 숫자(③)는 불 번짐과 총괄 AI 계획이 실행마다 달라 1회 값입니다.

### 5-4. 영상 ([구글 드라이브 폴더](https://drive.google.com/drive/folders/1mKf7SWaMMfgTkvHFlNM9OuFESxECjyqy), 가로 1280 px, 소리 없음. GIF는 저장소 `docs/ugv/media/`)

| 영상 | 시험 | 내용 | 길이 | 편집 |
|---|---|---|---|---|
| [01 통합 일반주행 4대 3D트윈](https://drive.google.com/file/d/1Ic2o8N6mWVAHP95pXV_fdyWmRf5ojPiC/view) | ③ 통합 환경 | 총괄 요청 출동 → 도착 → 관측 | 2분 30초 | 다른 화면 10초 잘라냄, 2배속 |
| [02 UGV단독 Swagger 평가·실행](https://drive.google.com/file/d/1bw5k8rbyBo672su-RLFyA5ibGpZNnINr/view) | ① UGV 단독 | Swagger 수행 가능성 평가 → 실행 → 도로 상황판 | 1분 22초 | 2배속 |
| [07 Gazebo 1대 직접지시 3D트윈·QGC](https://drive.google.com/file/d/1FDUeMzhDdScPLViCn4qkAXgzBJ7bsy9N/view) | ② Gazebo | 도로 상황판 직접 지시, 3D 화면·QGroundControl 동시 표시. UGV 2 m/s, 시뮬레이션 4배속 | 59초 | 없음 |
| [08 Gazebo 소방차 방수표시](https://drive.google.com/file/d/1LxS15i7fFwyW3IC_bP5gZEL3C1U2dunj/view) | 시험 아님 (Gazebo 단독, 부분 구현 기능) | Swagger `/suppress`로 방수 시작 → Gazebo 물줄기 | 33초 | 없음 |
| [09 최종통합 거절 도로상황판](https://drive.google.com/file/d/1gaAT6Zct-FrcqPuWq4ibnaslTJCdRTlK/view) | ④ 팀 저장소 트윈 | 거절 요청 → A-ugv1·B-ugv1 REJECT TARGET_UNREACHABLE이 기록 탭에 반복해 쌓임 | 90초 | 없음 (GIF는 30~90초 3배속) |
| [10 도로상황판 총괄 UGV출동요청](https://drive.google.com/file/d/1SY68U-cmPt6lgy0qlqBAr5AMy7e0-hpU/view) | ⑤ 팀 저장소 트윈 (`thermal`) | 도로 상황판에서 인제119 A 지점에 UGV 출동 요청 → 총괄이 A-ugv1 배정 → 평가 수락·경로 확정(11.3 km)·주행·도착 | 33초 | 없음 |

---

## 6. 실행 방법과 다른 파트 연결

### 6-1. 실행

**자동시험 · 경우별 재현** — 다른 서버 없이 UGV만으로 돕니다.

```bash
.venv/bin/python -m pytest tests/test_ugv_*.py -q                                   # 자동시험 5개
.venv/bin/python docs/ugv/evidence/2026-10-10/ugv_cases.py /tmp/ugv_cases.json      # 거절·실패 동작 18건 재현
```

**로컬 — 한 기계에서 전부**

```bash
# [A] 거절 시험 (5-2 final) — 팀 시연 시나리오 그대로(도로 시나리오 없음, AI 없음) + 시뮬레이션 40분에 거절 요청 1건 자동
bash ugv/tools/run_twin_ugv.sh final                   # main / dispatch / thermal 로 바꾸면 다른 구성 (5-2)
.venv/bin/python run_servers.py stop
#     거절 요청을 손으로: bash ugv/tools/run_twin_ugv.sh dispatch 로 켠 뒤 .venv/bin/python ugv/tools/twin_reject_request.py

# [B] UGV 서버만 (5-3 ①, Swagger·도로 상황판 확인용) — 도로 시나리오 변수를 주지 않으면 모든 도로가 뚫림
UGV_DRIVER=sim .venv/bin/python -m uvicorn ugv.server:app --port 8100

# [C] Gazebo 1대 (5-3 ②) — A-ugv1만 PX4, 나머지 sim. 총괄·트윈 없이 UGV 서버만 뜨고 도로 상황판에서 직접 지시
SPEED=4 ./ugv/tools/px4-start.sh A-ugv1                                              # WSL, PX4 빌드 필요
UGV_DRIVER=px4 UGV_PX4_RESOURCES=A-ugv1 UGV_TIME_SCALE=4 .venv/bin/python -m uvicorn ugv.server:app --port 8100
```

**원격 — UGV 서버를 다른 기계에서.** 총괄 쪽은 `config.py`의 `UGV_SERVER_URL`을 UGV 기계 주소로 바꿉니다. 명령은 로컬과 같고 주소 변수와 `--host 0.0.0.0`만 더합니다.

```bash
# [A'] 거절 시험 — 총괄·환경은 상대 기계. 거절 요청은 아무 기계에서나 --env/--orch 를 주어 실행
#      .venv/bin/python ugv/tools/twin_reject_request.py --auto --env http://<환경>:8300 --orch http://<총괄>:8200
UGV_DRIVER=sim UGV_ENV_URL=http://<환경>:8300 UGV_ORCH_URL=http://<총괄>:8200 \
  .venv/bin/python -m uvicorn ugv.server:app --host 0.0.0.0 --port 8100

# [C'] Gazebo 1대 — PX4 기계에서 UGV_HOST 로 UGV 서버 주소를 알려 줌
UGV_HOST=<UGV 기계> SPEED=4 ./ugv/tools/px4-start.sh A-ugv1
UGV_DRIVER=px4 UGV_PX4_RESOURCES=A-ugv1 UGV_TIME_SCALE=4 UGV_ENV_URL=http://<환경>:8300 UGV_ORCH_URL=http://<총괄>:8200 \
  .venv/bin/python -m uvicorn ugv.server:app --host 0.0.0.0 --port 8100

```

- 도로 시나리오(`UGV_SCENARIO`)는 UGV 서버만 읽습니다. 총괄·환경은 바꿀 것 없음
- Gazebo는 PX4 `SPEED` = `UGV_TIME_SCALE`로 맞춥니다. UGV 시계가 Gazebo 시간을 따르므로 배속 100 트윈과는 같이 돌리지 않습니다 ([0장 참조](#0-sim으로-결정한-이유))
- 주소: 3D 트윈 `http://<웹>:8080/inje3d`, 도로 상황판 `http://<UGV>:8100/view`, Swagger `http://<UGV>:8100/docs`

### 6-2. 누구와 무엇을 주고받나

| 상대 | 무엇을 |
|---|---|
| 총괄 → UGV | 상태 조회, 평가, 주행 시작, 진행 조회 |
| UGV → 환경 모듈 | 지금 시각 (`/health`) |
| 웹 관제판 → UGV | 차량 위치·상태 표시 |
| UGV → 총괄 | 도로 상황판에서 출동 요청할 때만 |

**총괄이 UGV를 쓰는 흐름** (통합 환경의 총괄 기준)

1. 출동 전 확인: 쉬고 있는 UGV마다 구역별로 수행 가능성 평가(PROBE)를 요청 → REJECT면 그 구역에서 뺌
2. 고른 차에 다시 수행 가능성 평가 → 실행
3. 진행 조회로 도착 확인
4. 도착 위치에서 모의 열화상 관측 (지형 시선 계산)

명령은 **총괄만** 내립니다. 도로 상황판의 직접 지시는 운영자 예외이고, 이때 총괄 임무는 실패(`OPERATOR_OVERRIDE`)로 닫혀 다른 차에 다시 맡겨집니다.

---

## 7. 발표에서 보여줄 동작

> 2026-10-12 기준으로 정리한 계획입니다 (영상 10, `2026-10-12_thermal` 시험).

드론과 겹치는 부분도 있으며 Gazebo 시연도 따로 있으므로, 발표 시간 관계상 UGV는 다음 두 가지면 충분하다고 봅니다.

1. **알고리즘** — 수행 가능성 평가와 Dijkstra 경로 ([3장](#3-어떻게-판단하나)) - ppt에 gif
2. **시연·영상 한 편** — 도로 상황판에서 특정 지점으로 출동을 요청하면 오케스트레이터가 알맞은 UGV를 골라 보내는 장면

![도로 상황판에서 인제119 A 지점에 UGV 출동 요청 → 오케스트레이터가 A-ugv1을 골라 배정 → 경로 확정·주행·도착](../ugv/media/ugv_roadview_orch_dispatch.gif)

영상: [영상 10](https://drive.google.com/file/d/1SY68U-cmPt6lgy0qlqBAr5AMy7e0-hpU/view) · 실행 결과 근거: [`2026-10-12_thermal`](../ugv/evidence/2026-10-12_thermal/)

직접 시연할 때는 아래를 돌리면 될 것 같습니다.

```bash
bash ugv/tools/run_twin_ugv.sh thermal
```
- 불이 확인되면 남전1리 마을회관·인제휴게소 방어 출동이 UGV로 나가고, 시뮬레이션 20분부터 불 칸으로 UGV 열화상 정찰이 나갑니다. 어느 UGV를 보낼지·갈 수 있는지·관측 판정은 오케스트레이터와 UGV가 정합니다.
- 도로 상황판(`http://127.0.0.1:8100/view`)에서 지점을 눌러 "UGV 출동 요청"을 보내도 오케스트레이터가 차를 골라 보냅니다 (위 영상).
- 끄기: `.venv/bin/python run_servers.py stop`

### 7-1. 미완성·미통합 기능의 발표 자료용 영상 (시연 동작 아님)

아래는 통합 시연에 들어가지 않는 **미완성·미통합 기능**입니다 ([2장](#2-구현한-것--안-한-것)). 일부는 동작까지 만들어져 있어, 발표 임팩트용으로 영상이나 다시 보기를 곁들일 수 있습니다.

| 내용 | 파일 | 비고 |
|---|---|---|
| Gazebo 1대 직접 지시, 3D 화면·QGroundControl 동시 표시 | [영상 07](https://drive.google.com/file/d/1FDUeMzhDdScPLViCn4qkAXgzBJ7bsy9N/view), GIF 0장 | 실제 차량 모델 주행 (UGV 2 m/s, 시뮬레이션 4배속) |
| 소방차 방수: Gazebo에서 소방차가 물줄기를 뿜음 (`/suppress` 호출) | [영상 08](https://drive.google.com/file/d/1LxS15i7fFwyW3IC_bP5gZEL3C1U2dunj/view), GIF 아래 | 부분 구현·미통합 (2장). 화면 표시만, 환경의 불은 꺼지지 않음 |


![Gazebo 소방차 방수 표시 (부분 구현, 미통합)](../ugv/media/ugv_gazebo_water.gif)

## 8. 가정과 한계

| 항목 | 가정·한계 |
|---|---|
| 관측 | UGV 센서 없음. 총괄 모의 센서가 도착 위치로 만듦 |
| 속도 | sim 시속 60 km (도로 최저 50 km/h) |
| 도로 상황 | 기본 시연에서는 통제·혼잡을 꺼서 모든 도로가 뚫려 있음 |
| 배터리 | 표시용 (sim 1 km당 1 % 감소). 0 %가 되어도 거절·정지하지 않음 |
| 이상 판정 | 60초 동안 10 m 미만 = 멈춤, 100 m 초과 = 경로 이탈 |
| Gazebo | 차량 모델 r1_rover 최고 2 m/s(약 7 km/h). 시연 배속에 맞추려면 시속 60 km 모델이 필요함 |
| 통합 환경 시험 | 5-3 ③④는 통합 환경(수진님 저장소의 총괄·환경, 5-1)에서 돌린 결과. 거절은 팀 저장소 트윈에서도 확인 (5-3 ④) |

**발표 이후 과제:** 배터리로 왕복 가능 여부 판단 · 환경 모듈과 연동한 소화(방수) 기능 구현 · Gazebo 차량 모델을 시속 60 km로 바꿔 시연 배속에 통합

---

## 9. 다시보기

**다시 보기 사용법** (도로 상황판 `/view`)

![도로 상황판 다시 보기: 위 실행 선택 → 아래 재생·배속](../../ugv/ugv_image/road_view_replay_usage.jpg)

1. 화면 위 실행 선택 칸에서 "과거 …" 실행을 고릅니다 (기본은 "실시간")
2. 화면 아래 ▶ 재생, 배속(60×)을 고르고 막대를 끌어 시각을 옮깁니다
3. 왼쪽 차량을 누르면 그 차의 경로와 구간별 소요시간, 오른쪽 기록 탭에서 평가 → 출발 → 진행 → 도착 사건이 보입니다

**어느 기록을 볼 수 있나 — 경우별**

| 상황 | 되나 | 방법 |
|---|---|---|
| 진행 중인 실행을 실시간으로 | 됨 | 선택 칸 "● 실시간" (기본) |
| 진행 중인 실행을 처음부터 다시 | **안 됨** — 목록에는 지난 실행만 뜨고 지금 실행은 빠짐 | 실행을 끝내고(아래) 다시 보기 |
| 끝낸 실행을 다시 보기 (시연에서 쓰는 방식) | 됨 | `run_servers.py stop` 뒤 UGV 서버만 띄우면 방금 실행이 "과거 …"로 목록에 뜸 (기록은 `ugv/.state/history`, 최근 30개) |

```bash
# 끝낸 실행 다시 보기 — 전체 시연을 끝낸 뒤 UGV 서버만
.venv/bin/python run_servers.py stop
UGV_DRIVER=sim .venv/bin/python -m uvicorn ugv.server:app --port 8100
# → http://127.0.0.1:8100/view 선택 칸에서 "과거 …" 고르기

```
- 다시 보기 기록(`ugv/.state/history`, 최근 30개)은 각자 기계에만 남고 저장소에는 올리지 않습니다 (`.gitignore`)