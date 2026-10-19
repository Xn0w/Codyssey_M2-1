# ADAIR — 물리 시뮬레이션 레포

ADAIR(산불 대응 UAV·UGV 협업 시스템)를 **물리 시뮬레이션으로 시험·검증하는 레포**입니다.
팀 레포([Xn0w/Codyssey_M2-1](https://github.com/Xn0w/Codyssey_M2-1))의 코드를 바탕으로 합니다. 거기에 Gazebo + PX4 SITL 차량 시뮬레이션,
디지털 트윈, 시험 도구·판정기와 시험 기록을 더했습니다. 팀 레포에는 `ADAIR` 브랜치로 올라가 있습니다 (PR 없음).

- 기본 브랜치: `feat/orchestrator-final`
- 시연용 안정 버전 태그: `demo-stable-20261019`
- 검증 중인 수정은 `verify/*` 브랜치에 따로 둡니다. 검증이 끝난 뒤에만 기본 브랜치에 합칩니다.

## 무엇을 시뮬레이션하나

| 대상 | 시뮬레이션 | 위치 |
|---|---|---|
| UGV·소방차 | Gazebo(gz sim) 지형·도로 월드 + PX4 SITL rover. 차체 동역학·조향·제동을 그대로 돌립니다. 물리 없이 빠르게 돌리는 `sim` 드라이버도 있습니다 | `ugv/` (`ugv/gazebo/`, `ugv/drivers/px4.py`, `ugv/drivers/sim.py`) |
| UAV | PX4 SITL 또는 mock 드론 | `uav/uav-agent` |
| 산불 | 2019 인제 산불 재현 CA 확산 모델 (지형·연료·기상) | `environment/` |
| 총괄 | 임무 생성, 후보 평가, Safety, 재평가, 관측 계획 | `orchestrator/` |
| 관제 | 3D 재현·관제판 웹 | `web/` |

## 실행

### 1. 디지털 트윈 (물리 없이 전체 시스템)
```bash
bash tools/run_twin.sh                  # 서버 6개 + 트윈 시계 (UAV mock, 100배속)
UAV_MODE=real bash tools/run_twin.sh    # UAV 는 PX4 SITL, 시계 1배속
```
| 서버 | 주소 |
|---|---|
| 환경 | `:8300` |
| UAV | `:8000`, `:8001` |
| UGV | `:8100` |
| 총괄 | `:8200`, 관제판은 `/board` |
| 웹 | `:8080/inje3d` |

트윈은 배속을 쓰기 때문에, 트윈에서만 켜는 임시 설정이 있습니다. 예: `ORCH_SAFETY_SNAPSHOT_RECHECK`. 자세한 내용은 `tools/run_twin.sh` 주석을 보세요.

### 2. Gazebo + PX4 차량 시험 (WSL Ubuntu)
```bash
./ugv/tools/px4-start.sh                                          # 월드 + 차량 + PX4 SITL 1대
python -m ugv.tools.road_test --target 38.0275 128.13328          # 단일 차량 도로 주행 시험
python -m ugv.tools.fleet_test separate                           # 4대(UGV·소방차) 동시 운용 시험
python -m ugv.tools.road_test --analyze logs/ugv/road_xxx.json    # 기록 다시 판정
```
- PX4-Autopilot 빌드가 필요합니다 (`~/PX4-Autopilot/build/px4_sitl_default`). PX4 소스는 고치지 않고, 우리 airframe 만 복사합니다.
- 판정은 Gazebo 실제 자세로만 합니다: 도착 거리, 곡선 횡가속, 차체 둘레 도로 이탈, 차량 간격, RTF.
- 여러 시험이 Gazebo·서버 포트를 같이 쓸 때는 `../.adair_port_lock` 잠금 파일로 순서를 맞춥니다. 규칙은 같은 폴더의 `.adair_port_lock.README` 에 있습니다 (레포 밖, 이 컴퓨터 한정).

### 3. 단위 시험
```bash
python -m pytest ugv/tests orchestrator/tests --ignore=orchestrator/tests/test_live_uav.py --ignore=orchestrator/tests/test_live_ugv.py
```

### 4. 통합 폐루프 (PX4·Gazebo 없이)
[INTEGRATION_README.md](INTEGRATION_README.md) 를 보세요 (`python run_integrated.py`).

## 폴더

```
ugv/            UGV·소방차 서버(:8100)·경로 계획(drive_graph, approach)·교통(traffic)·차량 감시(vehicle)
  gazebo/       월드·차량 모델 (adair_ugv, adair_firetruck)
  tools/        Gazebo 시험 하네스·판정기 (road_test, fleet_test, gz_track …)
  tests/        단위 시험
uav/            UAV Agent (PX4 / mock)
environment/    산불 확산 모델·환경 계약 서버(:8300)
orchestrator/   총괄 서버(:8200)
web/            3D 재현·관제판
tools/          디지털 트윈 실행(run_twin.sh)·트윈 시계·운영자
docs/           파트별 설계·검증 문서 (docs/ugv: 단계별 Gazebo 검증 기록)
logs/           시험 실행 기록 (logs/ugv/stage*: Gazebo 시험 결과·판정)
```
