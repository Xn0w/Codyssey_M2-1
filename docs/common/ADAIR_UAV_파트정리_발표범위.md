# ADAIR UAV 파트 정리 — 발표 범위 기준

- 담당: UAV(드론) — 김동현
- 기준: `main` @ `55edfd3` + UAV 파트 정리(2026-10-10). 실행 확인 2026-10-10 (WSL2, Python 3.14, PX4 1.18 SITL + Gazebo)
- 발표 범위: 환경모델의 화재를 UAV·UGV가 관측하고, 총괄이 이를 모아 인지 지도를 만드는 과정. 진화·살수는 제외
- 근거 파일: `docs/uav/evidence/2026-10-10_main/`, 영상: `docs/uav/media/`

---

## 1. UAV 파트의 역할

UAV는 총괄의 관측 요청을 **갈 수 있는지 판단**(ACCEPT / REJECT / COUNTER)하고, 수락한 요청만 비행해서 **언제·어디서·어떤 고도로 관측했는지** 보고합니다.

```
총괄 ──evaluate(갈 수 있나?)──▶ UAV ── ACCEPT / REJECT / COUNTER
총괄 ──execute(가라)─────────▶ UAV ── 상승 → 이동 → 관측 → 복귀 → 착륙
총괄 ◀──task 조회(관측 위치·시각)── UAV
```

시나리오대로 A·B 소방서에 2대씩, 모두 4대입니다. 기지 좌표는 팀 거점 파일 `environment/config/fire_stations.json`을 그대로 읽습니다.

| ID | 포트 | 모드 | 기지 | 발화점까지 |
|---|---|---|---|---|
| A-uav1 | 8000 | **real** (PX4 SITL + Gazebo) | A = 인제119 (38.0614, 128.1685) | 5.0 km |
| A-uav2 | 8001 | mock | A = 인제119 | 5.0 km |
| B-uav1 | 8002 | mock | B = 기린119 (37.9647, 128.3184) | 17.8 km |
| B-uav2 | 8003 | mock | B = 기린119 | 17.8 km |

- **mock**: PX4 없이 비행·배터리를 계산으로 흉내 냅니다(100배속). **real**: PX4/Gazebo에서 실제로 비행합니다.
- B 드론은 산맥 반대편이라 왕복 배터리가 모자라 `LOW_BATTERY`로 거절합니다. "가까운 자원이 항상 가능한 것은 아니다"를 보여 주는 정상 동작입니다.
- **발표 표현 주의:** "드론이 열화상으로 불을 찾았다"가 아니라 "드론이 관측 위치까지 비행해 위치를 보고했고, 관측 결과는 환경모델 기반 모의 센서로 만들었다"가 정확합니다.

---

## 2. 기능

### 2-1. 구현됨

| 기능 | 확인 |
|---|---|
| 상태 조회 (위치·배터리·비행모드·건강상태) | ✅ mock·real |
| 수행 가능성 판단 (거절 사유 13종 + COUNTER) | ✅ mock 전부, real |
| 실행: 상승 → 목표 이동 → 관측 체류 → 복귀 → 착륙 | ✅ mock, ✅ real 6회 (영상 있음) |
| 지형(DEM) 기반 순항고도: max(관측고도, 경로 최고 지형 + 50 m) | ✅ 자동시험, ✅ real (`terrain_check=OK`) |
| 같은 실행 요청 재전송 → 중복 출발 없음, 같은 키·다른 내용 → 409 | ✅ mock |
| 임무 중단(abort) | ✅ mock |
| 서버 재시작 뒤 실행 기록 유지 | ✅ 자동시험 |
| 총괄과 연동 (트윈 시연) | ✅ mock 2대, ✅ real 1 + mock 3 |

### 2-2. 구현하지 않은 것 (발표 범위 밖)

| 항목 | 설명 |
|---|---|
| 실제 센서로 화재 감지 | 시뮬레이션 기체(x500)에 카메라가 없음. real 관측값은 `NO_DATA`, mock은 자리표시값 |
| 자율 순찰 비행 | 총괄이 지점을 하나씩 요청 |
| real 모드 failsafe·통신품질·풍속 | PX4에서 읽지 않고 고정값 |
| real 2대 이상 | 발표 구성은 real 1대 + mock 3대 |
| 배터리 실측 보정 | 소모율 0.033 %/s는 추정치 |

---

## 3. API와 데이터 기준

UAV 1대 = 서버 1개. 전체 사양은 `uav/API_DEFINE.md`입니다.

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/health` | 동작 여부, 모드(mock/real) |
| GET | `/uav/{id}/state` | 현재 상태 (real은 응답에 4~5초) |
| GET | `/uav/{id}/capabilities` | 센서·관측 시간 범위 등 |
| POST | `/uav/{id}/evaluate` | 수행 가능성 판단 (비행 안 함) |
| POST | `/uav/{id}/execute` | 실행. 즉시 `STARTED`, 비행은 비동기 |
| GET | `/uav/{id}/task/{task_id}` | 진행·결과 (관측 위치 포함) |
| POST | `/uav/{id}/task/{task_id}/abort` | 중단 |
| POST | `/mock/set` | mock 전용. 배터리·바람·고장 상태 주입 (거절 시연용) |

**요청 예 (evaluate / execute 공통)**
```json
{"task_id": "T-1", "decision_id": "D-1",
 "target": {"lat": 38.0884, "lon": 128.1685, "alt_m_amsl": 570.0, "target_agl_m": 80},
 "wind_ms": 3.1, "observation_type": "THERMAL"}
```

**결과의 관측 부분** (총괄이 쓰는 값은 `position`, `observed_at`)
```json
"observation": {"observed_at": "2026-10-10T12:13:07Z",
  "position": {"lat": 38.0704, "lon": 128.1685, "alt_m_amsl": 352.7},
  "sensor_type": "THERMAL", "value_status": "NO_DATA"}
```

| 항목 | 기준 |
|---|---|
| 좌표 | WGS84 위도·경도 |
| `target.alt_m_amsl` | 목표 지점 **지면**의 해발고도(m). 없으면 `TARGET_ALTITUDE_UNKNOWN` 거절 |
| 관측 비행고도 | 지면 + `target_agl_m`(기본 80) + 10 m |
| `wind_ms` | 총괄이 환경 값을 넣어 줌. real은 없으면 `WIND_UNKNOWN` 거절 |
| `remaining_time_s` | (선택) 마감까지 남은 시뮬레이션 초 |
| `observe_duration_s` | (선택) 관측 체류 시간, 기본 60초 |
| 시각 | UTC ISO 8601, UAV 서버 시계 |
| 단위 | m, m/s, s, 배터리 % |
| task `status` | STARTED → IN_PROGRESS → COMPLETED(관측 끝, 복귀 시작) / FAILED |
| `physical_state` | ENROUTE / OBSERVING / RETURNING / LANDED 등 |

---

## 4. 총괄과 연결하기 (AWS)

UAV 서버 4개를 AWS EC2 한 대에 띄웁니다. real과 mock은 API가 같으므로 **총괄은 주소만 바꾸면 됩니다.**

**UAV 쪽 (EC2)**
```bash
bash uav/etc/px4-start-kangwon.sh          # PX4 SITL + Gazebo (창 없음), 인제119에 스폰
cd uav/uav-agent
UAV_ID=A-uav1 UAV_MODE=real PX4_ADDRESS=udpin://0.0.0.0:14540 ../../.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
UAV_ID=A-uav2 UAV_MODE=mock ../../.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8001 &
UAV_ID=B-uav1 UAV_MODE=mock ../../.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8002 &
UAV_ID=B-uav2 UAV_MODE=mock ../../.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8003 &
```
EC2 보안그룹은 TCP 8000~8003을 총괄 PC IP에만 엽니다.

**총괄 쪽**
1. 루트 `config.py`의 `UAV_ENDPOINTS`를 바꿉니다.
   ```python
   UAV_ENDPOINTS = {
       "A-uav1": "http://<EC2 IP>:8000",   # real
       "A-uav2": "http://<EC2 IP>:8001",   # mock
       "B-uav1": "http://<EC2 IP>:8002",   # mock
       "B-uav2": "http://<EC2 IP>:8003",   # mock
   }
   ```
2. 실행할 때 로컬 UAV를 띄우지 않도록 `--uav-url`을 주고, 3D 트윈에 4대를 그리도록 `TWIN_UAVS`를 줍니다.
   ```bash
   TWIN_UAVS="A-uav1=http://<EC2 IP>:8000,A-uav2=http://<EC2 IP>:8001,B-uav1=http://<EC2 IP>:8002,B-uav2=http://<EC2 IP>:8003" \
     .venv/bin/python run_servers.py start --twin --twin-speed 5 --uav-url http://<EC2 IP>:8000
   ```
3. 확인: `curl http://<EC2 IP>:8000/health` → `"mode": "real"` (8001~8003은 `"mock"`)

**배속:** real 드론은 실제 시간으로 납니다(인제 → 현장 왕복 약 20분). 트윈을 100배속으로 돌리면 그동안 환경이 너무 많이 진행되므로, real을 포함할 때는 `--twin-speed 5` 정도로 맞춥니다(로컬 확인 값).

`<EC2 IP>`는 배포 후 알려 드립니다. 같은 구성은 로컬에서 확인했습니다(§7-3).

---

## 5. 로컬 실행

```bash
# 준비 (처음 한 번)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-integrated.txt

# 전체 시연 (mock 2대) — 3D 트윈 http://127.0.0.1:8080/inje3d ("실시간 연결 LIVE")
.venv/bin/python run_servers.py start --twin
.venv/bin/python run_servers.py stop

# UAV 1대 실제 비행 (docker, px4io/px4-sitl-gazebo 이미지 필요. 창을 보려면 --gui)
bash uav/etc/px4-start-kangwon.sh
cd uav/uav-agent && UAV_ID=A-uav1 UAV_MODE=real ../../.venv/bin/python -m uvicorn main:app --port 8000
bash uav/etc/px4-stop.sh

# 자동시험
.venv/bin/python -m pytest tests/test_uav_requests.py tests/test_exec_idempotency.py -q
```
로컬 `--twin`에서는 mock 드론이 기지 대신 발화점 700 m 밖 차량 집결지에서 뜹니다(`UAV_HOME`).

---

## 6. 발표에서 보여줄 동작

### 6-1. 정상 동작

| 장면 | 보여주는 방법 |
|---|---|
| 실제 PX4 기체 비행 (상승 → 이동 → 관측 → 복귀 → 착륙) | 영상 `uav_px4_flight.mp4`, 또는 §5 실제 비행을 `--gui`로 |
| 총괄 요청을 받아 출동·관측 | 3D 트윈 LIVE |
| 능선을 넘는 순항고도 | evaluate 응답 `constraints.cruise_alt_m_amsl` |
| 같은 실행 요청 재전송 → 중복 출발 없음 | execute 두 번 → `duplicate:true` |

### 6-2. 거절·예외 동작 (mock에서 재현, 목표 = 인제119 북쪽 3 km)

| 상황 | 결과 |
|---|---|
| 강풍 (12 m/s) | REJECT `HIGH_WIND` (기준 10 m/s) |
| 다소 강한 바람 (9 m/s) | ACCEPT + 경고 `MODERATE_WIND` (8 m/s 이상) |
| 배터리 8% | REJECT `LOW_BATTERY` (필요 31.9%) |
| 배터리 50%, 관측 600초 요청 | **COUNTER** — 관측 152초로 줄이면 가능 |
| 산맥 반대편 기지 (B-uav1 → 발화점) | REJECT `LOW_BATTERY` (복귀 후 −37%) |
| 다른 임무 수행 중 / 복귀 중 | REJECT `BUSY` |
| 마감 지남 / 촉박 | REJECT `TIMEOUT` / `DEADLINE_TIGHT` |
| 목표 지면고도 없음 | REJECT `TARGET_ALTITUDE_UNKNOWN` |
| 없는 센서 요청 (LIDAR) | REJECT `REQUIRED_CAPABILITY_UNAVAILABLE` |
| failsafe / GPS 이상 / 통신 끊김 | REJECT `FAILSAFE_ACTIVE` / `SENSOR_FAILURE` / `COMMUNICATION_FAILURE` |
| 풍속 미제공 (real) | REJECT `WIND_UNKNOWN` |
| 같은 키로 다른 내용 실행 | HTTP 409 (기존 실행 유지) |
| 비행 중 중단 | `FAILED` / `ABORTED`, 복귀 |

판정 순서: `WIND_UNKNOWN` → `TARGET_ALTITUDE_UNKNOWN` → `FAILSAFE_ACTIVE` → `SENSOR_FAILURE` → `COMMUNICATION_FAILURE` → `BUSY` → `REQUIRED_CAPABILITY_UNAVAILABLE` → `HIGH_WIND` → COUNTER(관측 시간 축소) → `LOW_BATTERY` → `RETURN_MARGIN_INSUFFICIENT` → `TIMEOUT` → `DEADLINE_TIGHT` → ACCEPT

---

## 7. 테스트 결과 (2026-10-10)

### 7-1. 자동시험·mock 재현
- 자동시험 25개 전부 통과 (`pytest_uav.txt`)
- §6-2 표 전부 기대대로 (`uav_cases_mock.json`, `uav_counter_mock.txt`, 재현 스크립트 `uav_cases.py`)

### 7-2. PX4 SITL + Gazebo 실제 비행 — 6회 모두 성공

| 비행 | 출발 | 결과 | 근거 |
|---|---|---|---|
| INJE-1 | 인제119 → 북쪽 1 km, 관측 20초 | 약 7분, `COMPLETED` / `OBSERVED` / `LANDED`, `terrain_check=OK` | `uav_real_task_INJE-1.json`, `uav_real_track_INJE-1.csv` |
| RV-1~5 | 원통119 → 북쪽 1 km (기지 변경 전) | 5회 모두 `COMPLETED` / `OBSERVED` / `LANDED` | `uav_real_task_RV-*.json`, `uav_real_track.csv` |

- INJE-1의 스폰 위치 GPS(38.061376, 128.168474, 해발 199.3 m)가 거점 좌표·DEM과 일치했습니다.
- 영상 `uav_px4_flight.mp4`(RV-5, 100초 4배속), 장면 4컷 `uav_px4_flight_frames.png`

### 7-3. 트윈 시연 연동
- **mock 2대 (100배속):** 실행 110건 모두 `COMPLETED`, 평가 112건 모두 ACCEPT. 관측 위치를 모두 보고했습니다.
- **real 1 + mock 3 (§4 구성을 로컬에서, 5배속):** 총괄에 4대 등록, real A-uav1이 정찰을 자동 배정받아 `COMPLETED`, mock A-uav2도 `COMPLETED`. B-uav1은 `LOW_BATTERY`로 거절했습니다.

---

## 8. 가정과 한계

| 항목 | 내용 |
|---|---|
| 화재 관측값 | UAV 센서가 아니라 환경모델 기반 모의 센서가 만듭니다. UAV는 위치만 보고 |
| mock 열화상 값 | 312.5 ℃ 자리표시값 (`value_status=SIMULATED`). 판단 근거로 쓰지 않음 |
| 비행 모델 | 순항 10 m/s, 상승 3 m/s, 직선 경로 + 단일 순항고도 |
| 배터리 | 소모율 0.033 %/s, 복귀 후 15% 예비 — 추정치 |
| 바람 기준 | 10 m/s 이상 거절, 8 m/s 이상 경고 — 잠정값 |
| real 모드 | failsafe·통신품질·풍속은 고정값, `/state` 응답 4~5초, 임무는 실제 시간만큼 걸림 |

발표 이후 과제: 카메라 기체와 열화상 처리, 순찰 비행, real 다중 기체, 배터리 실측 보정
