# 박수진 — UGV·PX4/Gazebo·총괄 구현 및 연동 현황

문서 상태: **코드·기록 대조 및 발표 방향 확인 완료. 최종 실행 후보와 증거 영상은 시험 후 갱신**.

작성·제출 기준: **2026-10-12**. 담당 범위: UGV 재구현·차량 주행 검증, 총괄 오케스트레이터 및 관측 통합. UAV 비행 에이전트·환경 화재 모델 자체의 개발 현황을 대신 보고하는 문서는 아니다.

**발표 목표는 최신 D 계열 지면에서 UAV·UGV가 관측하고, 총괄이 관측을 누적해 환경모델의 화재 범위에 가까운 인지 지도를 만드는 과정이다. 최신 지면을 포함한 최종 통합 시연은 준비 중이다.** 기존 PX4·Gazebo 통합 시험의 성공을 최신 D 지면의 성공으로 옮겨 적지 않는다.

발표 방향 확정(2026-10-12, 박수진): **2019 시나리오 설정을 유지하고 관측 가능한 범위만 시연하며, LLM 관측 계획을 포함한 최종 통합을 목표로 준비한다.** 시연을 위해 임의 시험 화재로 교체하거나 환경 시간 간격을 줄이는 것을 기본 방안으로 삼지 않는다. 기존 성공 기록은 규칙 방식이며, 최신 D+LLM 조합은 재검증 전이다.

## 1. 전체 시연에서 맡는 역할과 발표 범위

### 이번 발표의 역할

1. 총괄이 신고·관측·자원 상태를 받아 관측 임무를 생성하고 UAV·UGV의 가능 여부를 평가한다.
2. UGV는 도로에서 도달 가능한 접근 지점을 정하고 PX4·Gazebo에서 주행·정지한다. UAV 이동은 UAV 에이전트를 통해 요청한다.
3. 이동·도착 상태와 관측 결과를 구분한다. 관측은 현재 모의 센서 어댑터에서 만들어 출처와 가정을 표시한다.
4. 총괄은 관측된 화재·기상 정보를 장부와 인지 지도에 반영하고, 필요한 추가 관측·재평가를 요청한다.
5. 환경의 화재 정답 지도와 총괄의 인지 지도를 별도로 표시하고, 발견율을 시간에 따라 비교한다.

환경의 화재 상태는 시뮬레이션 정답이지 실제 산불 측정값이 아니다. 현재 관측은 **환경 정답을 모의 센서의 관측 가능 범위로 제한해 생성한 결과**다. 실제 열화상 영상 탐지 성능을 주장하지 않는다.

### 포함·제외

| 포함 | 제외 |
|---|---|
| UAV·UGV의 관측 목적 이동, 화재 범위 인지·통합, 관측 계획과 결과 추적 | UGV·소방차 살수, 헬기 투하, 진화 효과·진화 자원 최적화 |
| 연결이 검증된 경우 소방차를 환경정보 센서 자원으로 활용 | 소방차가 연결됐다는 이유만으로 진화 기능을 시연 |
| 2019-04-04 산불 관련 지역·환경 설정 활용 | 당시 실제 화재 진행을 정확하게 재현했다고 단정 |

기존 코드에 `GROUND_SUPPORT` 등 진화로 오해할 수 있는 임무명이 있어도 이번 시연에서는 **지상 자원 접근·관측 지원**으로만 사용한다. 진화 이벤트·화재 상태 변경은 별도 기능이며 이번 발표의 정상 흐름에 넣지 않는다.

### 이번에 진행한 구현·검증의 흐름

- 차량 모델·PX4 airframe과 UGV 주행 모듈을 구성하고, 최고속도 목표와 구간 감속을 연결했다.
- 도로 기반 접근점·진행 방향 유지·회전 가능성·명령 교체·정지·복귀를 구현·수정하고 모의 시험과 Gazebo 시험을 나눠 확인했다.
- A·B 거점별 UGV·소방차 구성과 교통 조정을 추가하고, 평탄 월드에서 지형 월드로 시험 범위를 넓혔다.
- 총괄의 Task·decision·attempt 장부와 제공자 HTTP 연동을 이용해, UAV·UGV 출동부터 관측 반영·복귀·반납까지 연결했다.
- 지형 교차로 반복 실패를 비교시험으로 분석하고 D 계열 도로면을 개발 중이다. 기존 통합 결과를 최신 후보로 재검증하는 단계가 남았다.

각 항목은 본 문서의 상태표·증거 범위 안에서만 성과로 소개한다. 다른 파트의 원래 구현과 통합·수정 기여를 동일하게 표현하지 않는다.

## 2. 구현 상태와 실제 실행 확인 범위

상태 표기: **코드 구현 / 모의 시험 / PX4·Gazebo 실행 / 최종 시연 준비 중**을 구분한다. 과거 성공은 당시 코드·월드·경로에만 적용한다.

| 기능 | 구현 위치 | 확인한 범위와 남은 일 |
|---|---|---|
| 차량 모델·airframe | `ugv/gazebo/models/adair_ugv`, `ugv/px4/airframes/51100_gz_adair_ugv` | PX4·Gazebo 주행 기록 있음. 특정 실차·Prius 성능 재현 모델은 아님 |
| 도로망·방향·회전 제약 | `ugv/road_source.py`, `ugv/drive_graph.py`, `ugv/roads.py` | 코드 및 주행 시험 있음. 일방통행·차체·회전 조건, 즉시 U턴·후진 금지. 전체 도로 주행 검증은 아님 |
| 접근 지점·속도 계획 | `ugv/approach.py`, `ugv/roads.py` | 최고 목표 60 km/h, 곡선 감속·화재 경계 100 m 이격. 평탄 월드 장거리 시험에서 3초 유지 최고 60.3 km/h 기록. 최신 D 지형 전체의 60 km/h 검증은 아님 |
| 명령 교체·정지·복귀 | `ugv/vehicle.py`, `ugv/drivers/px4.py` | PX4·Gazebo 시험 있음. 교차로 정차 후 재출발·막힘·간헐 인계 실패 등 잔여 결함 존재 |
| 차량 4대 구성 | `ugv/fleet_ab.json`, `ugv/traffic.py` | A·B 각각 UGV 1대·소방차 1대 구성과 과거 운용 시험 있음. 최신 D 지면 최종 조합은 미검증 |
| 지형·도로 충돌면 | `ugv/tools/build_terrain_tiles.py` | 전체 타일 생성·정적 검사와 표본 주행 시험. D 계열은 별도 개발 작업 트리에서 개선 중이며 운영 채택 미확정 |
| 총괄 평가→Safety→실행→추적 | `orchestrator/engine.py`, `resources.py`, `safety.py`, `ledger.py` | 계약·모의 시험 및 지정 조건의 UAV 1대+UGV 1대 PX4 통합 기록 있음 |
| 화재·기상 모의 관측 | `orchestrator/observation.py`, `config.py`, `knowledge.py` | 코드 있음. 센서 영상 없음, `SIMULATED`·`TEST_ONLY` 표시. 이동 중 연속 관측·확산 시 자율 순찰은 최종 조합에서 별도 검증 필요 |
| 인지 지도·추가 관측 계획 | `orchestrator/observation_planner.py`, `engine.py` | 관측 누적·계획 코드 있음. LLM 계획 경로와 규칙 대체 경로 구분 필요. 최신 D 지면에서 지도 발견율 개선의 종단간 시연은 준비 중 |
| 정답 대비 지도 평가 | `orchestrator/map_evaluation.py`, `api.py` | 테두리·불타는 곳·화재 영역 발견율 계산 및 조회 구현. 최종 시나리오의 수치는 재실행 후 제시 |
| 살수·진화 | 이번 보고 대상 제외 | 발표 성과로 주장하지 않음 |

### 버전 경계

- 기존 통합 근거: `38aa911`, 기록 정리 `30a2048`, 주 저장소 확인 시 HEAD `5eda174`.
- 지면 원인 비교: `ADAIR_wt_turn`, `wip/turnaround`, `30457e7`.
- 정체·정지 수정: `ADAIR_wt_fix`, `wip/stop-pass`, 확인 시 `d8cb97c`.
- D 지면 개발: `ADAIR_wt_d`, `wip/design-surface`, 확인 시 `1540158`.
- 위 작업 트리의 개선이 주 브랜치에 모두 통합됐다고 가정하지 않는다. 발표 후보는 코드·모델·airframe·타일·설정을 묶어 확정하고 재시험한다.

## 3. 입력·출력 및 좌표·시간·단위·ID

### 연결 계약

| 경계 | 입력 | 출력·확인 사항 |
|---|---|---|
| 환경 → 총괄 | `run_id`, `state_version`, `map_version`, `simulation_time_s`, 지도 셀·신고·환경 값 | snapshot 유효성 검사. 다른 run·역순 자료 혼용 방지 |
| 외부 → 총괄 | `request_id`, `incident_id`, `kind`, `target`, `requirements` | `task_id`, 판단·실행시도·보류 사유. HTTP 202는 접수이며 도착 성공 아님 |
| 총괄 → UGV | `task_id`, `decision_id`, 목표·자원 조건. 정확한 제공자 형식은 `orchestrator/resources.py`의 `UgvClient` 사용 | 평가·실행 ACK/거절, 경로·ETA·접근점·남은 거리·고장·정지 상태 |
| 총괄 → UAV | 자원별 HTTP 평가·실행·상태·취소 | 비행 에이전트의 이동·도착·복귀 상태. UAV의 고정 mock 관측값은 탐지 근거로 사용하지 않음 |
| 관측 → 총괄 → 환경 | `observation_id`, `run_id`, `task_id`, `attempt_id`, `resource_id`, 관측 시각·위치·범위·값·출처 | 환경 APPLY ACK와 장부 기록. ACK·관측·물리 도착을 별도로 추적 |
| 총괄 → 관제·평가 | Task·attempt 상태, 인지 지도·관측 계획, 발견율 | `/state`, `/observation_plan`, `/evaluation`, `/board` |

UGV의 `/ugv/{rid}/observation`은 현재 **ROAD_STATUS**다. 이 응답을 열화상 화재 관측으로 해석하지 않는다. 화재·기상 모의 관측은 총괄 어댑터 경로를 사용한다.

### 기준

| 항목 | 현재 기준과 주의 |
|---|---|
| 외부 위치 | WGS84 `lat`, `lon`, degree. 환경 셀은 `cell_id`와 함께 전달 |
| 원자료 환경 지도 | EPSG:5186. UGV 지역 좌표와 직접 섞지 않음 |
| UGV 도로·월드 좌표 | 공통 datum 중심 횡메르카토르, x=동·y=북, m. PX4/Gazebo ECEF 접평면과 차이가 있어 `ugv/geo.py`의 `GZ_FRAME` 변환 사용 |
| datum | 위도 38.011200, 경도 128.122643, 해발 172.1 m. 월드·PX4·브리지 일치 필요 |
| 높이 | 지면 해발 `ground_amsl_m`, 비행 지면고 `target_agl_m`, Gazebo 로컬 z 구분. DEM 수직 기준 미확인 한계 표시 |
| 시간 | 환경 진행은 `simulation_time_s`, 로그는 실제 시각. PX4 최종 시연 목표 배율 1. UGV 통신 단절 600초·정지 후 1800초 정책은 **실제 단조시계** 예외로 명시 |
| 거리·속도 | m·m/s. 화면 km/h 변환은 ×3.6. 최고속도와 곡선 속도를 구분 |
| 기상 | `wind_ms` m/s, `wind_dir_deg` 북 기준 시계방향의 **불어오는 방향**, `temperature_c` °C, `humidity_pct` %. 환경이 주지 않은 값은 생성하지 않음 |
| 자원 ID | `A-uav1`, `A-ugv1`, `A-fire1`, `B-ugv1`, `B-fire1`. 종류는 `UAV`, `UGV`, `FIRE_ENGINE` |
| 식별·멱등성 | run / Task / decision / attempt / observation 분리. 재판단과 동일 요청 재전송을 구분 |

거점 좌표의 단일 출처는 `environment/config/fire_stations.json`이다. A=인제119안전센터, B=기린119안전센터. 파일의 `coordinate_status`는 현재 **UNVERIFIED**이므로 실제 소방서 좌표 확정으로 표현하지 않는다. 차량은 검증된 도로 대기점에서 스폰할 수 있으며 건물 좌표와 동일하다고 주장하지 않는다.

## 4. 실행 방법·설정·포트·순서

### 실행 경로 구분

- 루트 `run_integrated.py`: PX4 없는 초기 통합 예제. UAV mock·UGV in-process 경로가 포함돼 이번 물리 주행 시연의 실행 명령으로 사용하지 않는다.
- `integration/px4_live/run_integ.py`: 같은 월드의 PX4 UAV·UGV와 환경·총괄을 기동하는 기존 실기동 도구.
- **현재 도구 PROFILE은 기존 `tz_a33`·`tiles` 기준이다. D5 타일·월드로 자동 전환되지 않는다.** 최신 D 후보용 명시적 프로파일·스폰 높이·부분 도로망을 마련하고 검증한 뒤 발표용 명령을 확정해야 한다.

### 준비 조건

Windows + WSL Ubuntu-24.04, 설치·빌드된 PX4 SITL·Gazebo, 저장소 루트 `.venv`, 도로 GPKG·DEM·지형 타일·스폰 자료가 필요하다. 기존 실행 기록 버전은 PX4 `v1.18.0-beta1-446-g21fa379fb8`, Gazebo Sim `8.15.0`, Python MAVSDK `4.0.5`다.

```powershell
# 저장소 루트에서. 기존 가상환경이 없을 때만 생성
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-integrated.txt
# UAV real 연결은 UAV 파트의 의존성·MAVSDK 설치 안내도 적용
```

의존성 전체가 위 requirements 한 파일에 고정됐다고 가정하지 않는다. UAV 안내는 `uav/README.md`, 기존 통합 상세는 `docs/intergration/04. PX4 실기동 통합 시험 (2026-10-11).md`를 함께 확인한다. API 키는 공유 문서·로그에 넣지 않는다.

### 기존 프로파일의 실행 명령 — 최신 D 시연 완료 명령이 아님

```powershell
.\.venv\Scripts\python.exe integration/px4_live/run_integ.py preflight
.\.venv\Scripts\python.exe integration/px4_live/run_integ.py pretest --minutes 15 --ugv-lat-accel 1.0
.\.venv\Scripts\python.exe integration/px4_live/run_integ.py run --minutes 20 --ugv-lat-accel 1.0
# 도구가 띄운 프로세스를 종료할 때
.\.venv\Scripts\python.exe integration/px4_live/run_integ.py stop
```

`--minutes`는 실행 상한이며 준비 시간·조기 완료 때문에 영상 길이와 같지 않다. `--dry`는 UGV sim·UAV mock이므로 PX4 증거에서 제외한다. 기존 `preflight`도 잔류 PX4 정리 경로가 있으므로 다른 주행 시험과 동시에 실행하지 않는다. 이 문서 작성 중에는 실행하지 않았다.

LLM 관측 계획을 켜는 기존 옵션은 `--llm-planner`다. 최종 D용 프로파일을 준비한 뒤 이 옵션을 포함해 재검증한다. 현재 도구에 옵션만 붙여 실행하는 것으로 D 지면 전환·넓은 화재 범위 관측·최종 발표 시나리오가 구현되는 것은 아니다. LLM 호출 성공, 유효 계획, 규칙 대체 여부, 실제 배정·관측 결과를 따로 기록한다. 키·서버 설정은 `orchestrator/llm.py`와 `config.py`를 따르며 비밀 값은 문서에 넣지 않는다.

### 서버와 실행 순서

| 구성 | 포트·주소 | 설정·역할 |
|---|---|---|
| Gazebo·PX4 | UAV 인스턴스 0, UGV 인스턴스 1 | 같은 월드·datum·partition. airframe UAV 4001, UGV 51100 |
| 환경 | HTTP 8300 | `environment.server:app`, 시나리오·seed·발화·신고 설정 |
| UGV | HTTP 8100, MAVLink UDP 14541 | `UGV_DRIVER=px4`, `UGV_VEHICLES_JSON`, `UGV_ENV_URL`, `UGV_ROAD_SUBSET`, `UGV_TIME_SCALE=1` |
| UAV | HTTP 8000, MAVLink UDP 14540 | UAV 에이전트 `main:app`, `UAV_MODE=real`, `PX4_ADDRESS` |
| 총괄 | HTTP 8200 | `python -m orchestrator.api`, `ORCH_ENV_MODE=team_http`, `ORCH_ENV_URL`, `ORCH_UAV_ENDPOINTS_REPLACE=1`, `ORCH_UAV_ENDPOINTS`, `ORCH_UGV_SERVER_URL` |
| 관측·복귀 설정 | — | `ORCH_UGV_THERMAL`, `ORCH_OBS_PLANNER`, `ORCH_UGV_RETURN_HOME`, 센서 profile을 실행 기록에 고정 |

도구의 실제 준비 순서는 **공유 월드/PX4 → 환경 서버 → UGV·UAV 서버와 준비 확인 → 총괄 → 궤적 기록·환경 시계**다. 구체 순서는 `run_integ.py`를 기준으로 한다. 관측·복귀 설정은 연결만으로 기능 검증이 보장되지 않는다.

다른 작업의 8301 서버를 종료하지 않는다. 4대용 UGV MAVLink는 14541~14544로, UAV의 14540과 중복시키지 않는다.

## 5. 다른 파트와 연결되는 지점

| 상대 | 연결과 책임 경계 |
|---|---|
| 환경 | `/snapshot` 읽기, `/advance` 명시적 진행, `/apply` 관측 ACK, `/map_cells`, `/reports`. `orchestrator/team_env.py`가 어댑터. 관측 반영으로 정답 화재 상태가 바뀌는 것을 인지 개선과 혼동하지 않음 |
| UAV | `orchestrator/resources.py`의 HTTP 평가·실행·상태·취소. UAV팀 비행 기능과 총괄의 모의 관측 구분 |
| UGV | `/ugv`, `/ugv/{rid}/evaluate`, `execute`, `state`, `task/{task_id}`, `task/{task_id}/abort`, `route`, `events`, `stop` |
| 관측 통합 | `observation.py` → 지식·belief layers → 환경 ACK·추가 계획. 관측 위치·시간·coverage와 미관측을 기록 |
| 관제 | 총괄 8200의 `/board`, `/observation_plan`, `/evaluation`. 기존 web 8080의 UGV 화면 보간을 물리 주행으로 취급하지 않음 |

총괄 요청의 예시 형식은 아래와 같다. 위경도·셀 ID는 **활성 환경 `/map_cells`에서 확인한 동일 셀**로 교체한다. 예시를 넣었다는 이유로 최종 관측 시연이 검증된 것은 아니다.

```json
{
  "request_id": "DEMO-RECON-001",
  "incident_id": "INC-DEMO",
  "kind": "RECON",
  "target": {"lat": 38.0, "lon": 128.1, "cell_id": "COL_ROW"},
  "requirements": {
    "resource_types": ["UGV"],
    "sensor": "THERMAL",
    "extra_sensors": ["WEATHER"],
    "needs_env_ack": true
  },
  "dispatch": true
}
```

전송 경로는 총괄 `POST /tasks`다. 상태는 반환된 `task_id`의 `/tasks/{task_id}`와 `/tasks/{task_id}/events`에서 확인한다. 직접 UGV 호출과 총괄 경유 호출은 별도 시험으로 기록한다.

## 6. 발표에서 보여줄 정상 동작과 실패·거절 동작

### 정상 흐름 — 최종 D 조합은 시연 준비 중

1. 환경의 화재 정답 지도와 총괄의 초기 미관측 지도를 분리해 표시한다.
2. 신고를 계기로 관측 Task를 만들고 평가 → Safety → 실행 순서를 보여준다.
3. UAV·UGV 이동은 PX4 상태와 Gazebo 궤적으로 확인한다. UGV는 검증된 경로와 안전한 정차점을 사용한다.
4. 관측 범위·가시성 안의 화재 셀과 환경 값을 총괄에 반영한다.
5. 관측 전후 인지 지도와 발견율 시계열을 보여준다. 신고·가설·관측 확정을 구분한다.
6. 필요한 추가 관측과 복귀를 수행하고, 정지·착륙 확인 후 자원 반납을 추적한다.

평가 코드는 ① 테두리 재현율, ② 현재 불타는 곳 발견율, ③ 누적 화재 영역 발견율을 계산한다. **오탐을 포함한 종합 지도 정확도나 IoU를 검증한 값은 아니다.** 분모 0은 N/A다. 화재가 확산되면 발견율이 내려갈 수도 있으므로 단조 증가를 성공 조건으로 삼지 않는다. 평가용 정답을 관측 계획에 넘기지 않는 설계이며 최종 실행 로그에서도 이 경계를 확인한다.

### 실패·거절

| 사례 | 보여줄 동작 |
|---|---|
| 도달 불가·방향·회전 제약 | 무리한 U턴 없이 사유를 보고하고 거절·보류 |
| 화재 안전거리·환경 자료 불비 | 출동 거절 또는 정지. DANGER가 탈출 성공·안전 확보를 뜻하지 않음 |
| 중복 요청 | 같은 요청으로 중복 출동하지 않음 |
| 통신·관측 불확실 | UNKNOWN·미확인으로 기록하고 점유 유지. 도착·관측 성공으로 만들지 않음 |
| 차량 고장·정지 명령 실패 | 고장·재시도·실제 정지 확인을 기록하고 정상 완료와 구분 |

발표용 거절 사례도 최종 조합에서 사전 재현한다. 실제 시간 600초 + 정지 후 1800초 통신 단절 정책 전체는 20분 발표로 검증할 수 없으므로 과거 기록·논리 시험과 구분한다.

## 7. 실제 시험 결과와 로그·영상 위치

### 과거 실행 근거

| 시험 | 결과와 한계 | 증거 |
|---|---|---|
| UGV 평탄 장거리·복귀 | 약 13km, 3초 유지 최고 60.3km/h. 차체 이탈 최대 0.33m도 기록돼 무이탈 시험으로 주장하지 않음 | `docs/ugv/evidence/summary_G1_long_return.json`, `logs/ugv/G1_long_return_20261010_085131.{json,csv}` |
| UAV+UGV+총괄 실기동 | `38aa911`, 기존 tz_a33 지형, UAV 1대+UGV 1대. UGV 이탈 0·전복 0, UAV 최소 지형 여유 85.2m, Task 2건 완료·두 자원 반납 | `logs/integ/run_20261011_181821/analysis.json`, `orch_final.json`, `preflight.json`, `timeline.jsonl`, `orch.sqlite3` |
| 위 시험 궤적 | UAV·UGV Gazebo 좌표 CSV와 그림. 최신 D 지면이 아님 | 같은 폴더 `track_x500_0.csv`, `track_adair_ugv_1.csv`, `trajectory.svg`, `logs/integ/final5.out` |
| UAV 취소·중복·링크 단절 | 지정 조건에서 비행·귀환·착륙과 복구 후 상태 대조. 전체 UAV 성능 검증 아님 | `logs/integ/p1_mission/`, `p2_abort_dup/`, `p4_link/`; 상세 통합 보고서 참고 |
| 실제 시간 통신 단절 | 600초 후 정지, 정지 후 1800초에 복귀 시작. 긴 귀로의 도착은 기록 내 미확인 | `docs/ugv/UGV_검증보고서_24h.md` 4절 |
| 자동시험 | 기존 후보 613 passed·8 skipped는 당시 보고값. 최신 코드 전체 합격 수로 사용하지 않음 | `docs/intergration/04. PX4 실기동 통합 시험 (2026-10-11).md` |

**기존 통합은 약 20분 운용을 목표로 했으며 final5는 1082.5초에 두 자원 반납을 확인하고 종료했다.** 시험 발화 셀 46_48은 명시적인 시험 사건이며 실제 2019 발화점이 아니다. CA 주 갱신 2100초여서 이 실행은 불타는 셀 한 개를 사용했다. 따라서 확산되는 화재 범위를 여러 관측으로 복원하는 최종 성과의 근거로는 부족하다.

### 최신 D 계열 — 진행 중인 결과

아래는 **2026-10-12 15:35경 저장된 원본 확인값**이며 chain51 최종 결과가 아니다.

- D5 생성 성공 236/303. D2는 64/308로 분모가 다르다.
- 교차로 횡경사 6% 초과 도로: v2 107, D2 106, D5 247. D5 신규 초과 141, 해소 1. 생성 성공을 설계 기준 합격으로 해석하지 않는다.
- 저장된 18회: 도착 15회, 차체 경계 이탈 없이 도착·정지 11회.
- j494866·j495039·j494943은 각 3/3 이탈 없이 도착·정지했다.
- j495759·j495731은 각 3/3 도착했지만 경계 이탈 없는 회차는 각 1/3이다.
- j494846은 생성이 거절돼 기존 level 처리가 남았고 3/3 실패했다. 검증된 운행 구간으로 취급하지 않는다.
- 정상 교차로 대조·남은 문제 지점·정적 악화 구간·최종 코드 장거리·A↔B 연결은 계속 검증한다.

원본은 `logs/ugv/stage5/tiles_v2_D5all/tiles.json`, `static_checks.json`, `logs/ugv/stage4/chain51.sh`, `c51_*.out`이다. 상세 주행 JSON/CSV는 별도 작업 트리 `ADAIR_wt_turn/logs/ugv/c51*`에 있어 이 저장소를 clone하는 것만으로 확보되지 않는다. 공유할 증거를 선별해 저장소 또는 팀 공유 공간으로 옮기는 작업이 남아 있다.

영상·공유 자료: **현재 시험을 마친 뒤 최종시험 후 첨부 예정**(박수진 확인, 2026-10-12). 궤적 그림·CSV를 영상 촬영 완료로 표현하지 않는다. `logs/`와 생성 타일은 Git 관리 밖일 수 있으므로 공유 전에 필요한 자료의 추적·업로드 여부와 링크를 확인한다.

## 8. 모의값·가정·알려진 한계와 남은 작업

### 가정과 한계

- 열화상 영상·물리 카메라 없음. 관측은 `source=SIMULATED`, 센서 profile `TEST_ONLY`다.
- 지상 모의 관측은 360도, 마스트 높이 3m, 최대 2km다. **현재 코드는 600m 안을 항상 보이는 것으로 가정하고, 600m~2km에 지형 차폐를 적용한다.** 최대 2km 전역에서 지형 가시성을 검사하는 구현과 다르다. 발표 전 예외 유지 여부를 결정하고 유지하면 화면·자료에 표시한다.
- 건물·수목·연기 차폐, 열화상 해상도·오탐 모델 미반영.
- 기상은 환경 값 또는 기상청 ASOS 과거 자료 재생을 활용한 모의 관측이다. 차량 탑재 기상계의 실측이 아니다.
- 도로 폭은 차로 수 기반 추정값이다. 90m DEM을 약 0.977m 높이장으로 보간해도 원자료 정확도가 높아지는 것은 아니다.
- D5는 지형 추종 중심면과 접속 처리 후보이며 도로 설계 기준 전면 적합·전체 도로 안전·실차 전용 가능성을 보장하지 않는다.
- LLM은 관측 계획 후보 생성에 활용하며 차량의 직접 조향 제어가 아니다. 기존 실기동 통합은 LLM 관측 계획 OFF로 확인했다. 발표 목표는 ON이며, 시간 초과·잘못된 계획·규칙 대체 동작까지 확인해야 한다.
- 고장 후 다른 차량에 인계하는 sim 반복시험은 수정 전 3/20, 수정 후 4/20 실패했다. 해결 완료가 아니며 최종 다중 차량 통합 전 원인·대응 확인이 필요하다.

### 발표까지 남은 순서

1. chain51 최종 판정과 정상 대조, D5 정적 악화·미해결 교차로를 정리한다.
2. 발표용 D 후보·안전한 경로·최신 코드 설정을 고정하고 필요한 수정을 통합한다.
3. 최신 지면용 통합 프로파일·스폰·도로 부분집합을 명시하고 단일 차량 왕복·정지를 먼저 확인한다.
4. 2019 시나리오 설정을 유지한 채 실제로 관측 가능한 범위에서 LLM 계획 → 평가·Safety → 이동 → 모의 관측 → 인지 지도 → 추가 관측·평가를 종단간 검증한다. 환경 갱신 간격·시간 배율과 PX4 시간을 기록한다. 시연 시간 안에 화재 확산이나 충분한 지도 변화가 나타나지 않으면 그 한계를 그대로 보고하고 임의로 성과를 확대하지 않는다.
5. 이동 중 관측, 600m 예외, 기상 적용, 필요 시 소방차 센서 연결을 확인한다. 미달 기능은 발표 범위에서 명시적으로 제외한다.
6. 정상 사례·거절 사례·지도 전후 비교·평가 시계열·궤적·영상을 재현 설정과 함께 공유한다.

### 최종 시연 확인 대기

- 최종 D 버전·코드 커밋·경로·실행 명령: 시험 후 확정.
- 시나리오 방향은 2019 설정 유지·관측 가능한 범위, LLM 사용으로 확정. 구체 시작 시각·대상 영역·임무·시간 배율·실행 옵션은 최종 프로파일과 기록으로 확정.
- 최종 영상과 GitHub에서 내려받을 수 있는 증거 위치: 현재 시험 종료·최종시험 후 첨부 예정.

위 항목은 검증된 기능의 누락 정보가 아니라 **최종 시연의 미확정 사항**이다. 별도 확인 없이 완료로 바꾸지 않는다.

![비행하는 UAV](https://github.com/Xn0w/Codyssey_M2-1/blob/main/docs/common/image/05_50_44.png?raw=true)

![도로 위 UGV](https://github.com/Xn0w/Codyssey_M2-1/blob/main/docs/common/image/스크린샷%202026-10-12%20162612.png?raw=true)

