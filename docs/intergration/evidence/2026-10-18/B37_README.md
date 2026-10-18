# 묶음 3 · 묶음 7 시험 근거 (2026-10-17~18, UGV 담당)

맥 로컬에서 `python run_servers.py start --twin` 으로 돌린 실행 5회의 기록에서 뽑은 근거다.
실행 기록 원본(orchestrator.sqlite3, UGV history, 캡처, 영상)은 크기 때문에 저장소에 올리지 않고 담당 맥에 보관한다.

## 실행

| 실행 | 브랜치 · 커밋 | run_id | AI | 불 | 장면 |
|---|---|---|---|---|---|
| L3 | main `94a02b2` | RUN-INJE-20261017T085505Z-c033b7 | LLM 27회 | 발화 1칸 (약 1.75시간 뒤 소멸) | 없음 |
| N2 | fix/twin-legacy-fire-config `82155ed` | RUN-INJE-20261017T102254Z-ee7f06 | 규칙 대체 | 번짐 | 없음 (반복 1) |
| N3 | fix/twin-legacy-fire-config `82155ed` | RUN-INJE-20261017T105818Z-939c12 | 규칙 대체 | 번짐 | 없음 (반복 2) |
| N1 | fix/twin-legacy-fire-config `f2c4802` | RUN-INJE-20261017T235653Z-653bb5 | 규칙 대체 | 번짐 | 가린 칸 · 먼 칸 · 드론 끄고 정찰 · 총괄 재시작 |
| N4 | fix/twin-legacy-fire-config `f2c4802` | RUN-INJE-20261018T011018Z-91da8c | 규칙 대체 | 번짐 | 목표 도로 차단 · 주행 중 앞길 차단 |

공통: UAV mock 2대 · UGV sim 4대(UGV 2 · 소방차 2) · 100배속 · 관측 계획 ON · 귀소 ON(UGV만) · 환경 1분 단위 진행 · 신고는 발화 후 시뮬레이션 120초.
브랜치는 main 에 트윈 화재 설정(legacy CA) 6줄과 상황판 표시 수정만 더한 것이고 UGV·총괄 판정 로직은 main 과 같다.
규칙 대체 실행은 `ORCH_SKIP_DOTENV=1 python run_servers.py start --twin`.

## 파일

| 파일 | 만든 방법 | 확인할 내용 |
|---|---|---|
| `B37_summary_<실행>.txt` | 서버를 끈 뒤 시험 도구 `summary.py` 로 총괄 기록(orchestrator.sqlite3)·UGV 기록(ugv/.state/history) 요약 | 묶음 3·7 항목별 숫자: 지상 지원, 평가 판정, 보류 사유, 진화 없음, 귀소, 임무 수, 평가 누락, 중복, 복구 스캔 |
| `B37_probe_<실행>.txt` | 실행 중 시험 도구 `probe.py` 가 10초마다 env·ugv·orch·web `/health` 응답 시간과 시계를 기록, 끝난 뒤 요약 | 서버별 응답 시간(앞 1/3 → 뒤 1/3), 실패, 환경 시계 정지, UGV 시계 차이 |
| `B37_scenes_N1_N4.txt` | 서버를 끈 뒤 DB 사본에서 장면 임무의 이벤트를 순서대로 추출 | 3-6 가린 칸 보류, 3-5 먼 칸·도로 차단 거절과 우회, 3-4 드론 없이 UGV 대체, 7-6 재시작 복구 |
| `B37_cross_runs.txt` | 같은 방법으로 5회 실행을 나란히 비교 | 진행 중 총괄 응답, Safety 판정(자원×임무), Safety 판정 3등분과 평가→Safety 걸린 시간, N2·N3 환경 끝 상태 동일, 드론 시도 상태 반복 |

## 장면 만드는 방법 (사람 역할 요청만, 팀 코드 변경 없음)

- 3-6 가린 칸: 도로에서 0.8~1.8 km, 도로 지점에서 지형에 가린 칸을 골라 `POST /tasks` (RECON, resource_types=["UGV"], sensor=THERMAL)
- 3-5 먼 칸: `python ugv/tools/twin_reject_request.py` (도로에서 2.2 km 넘는 칸)
- 3-4 드론 없음: `python run_servers.py stop uav1 uav2` 뒤 `POST /tasks` (RECON, resource_types=["UAV","UGV"]), 약 75초 뒤 `restart uav1 uav2`
- 7-6 재시작: `python run_servers.py restart orch`
- 3-5 도로 차단: UGV 서버 `POST /roads/{road_id}/block {"blocked": true}` 로 목표 지점 도로를 막고 UGV 정찰 요청, 90초 뒤 해제
- 3-5 우회: 주행 중 UGV 의 `/ugv/{id}/route` 남은 구간 중 하나를 같은 방법으로 막고 60초 뒤 해제

## 알려 둘 점

- **UGV 우회 한계:** UGV 우회는 도로 중간에서 바로 돌아서지 못하고, 지금 달리는 도로 끝까지 간 뒤 새 경로로 간다(`ugv/agent.py` `reroute`, 끝 노드부터 재탐색). 도착은 정상이고 손해는 그 왕복 거리뿐이다(N4 B-ugv1 우회에서 약 4 km). 발표 뒤 도로 중간 회차 개선 검토.
- **출동 지연:** 출동 직전 안전 확인(Safety)이 평가와 확인 사이에 환경이 1분 넘어가면 "환경 바뀜(SNAPSHOT_CHANGED)"으로 다시 평가한다. 트윈 100배속에서는 자주 걸려 출동이 늦어진다(N1 드론 없을 때 정찰은 시뮬 약 10시간 늦게 출동). 잘못된 출동·중복은 없음. LLM 사용 시에는 LLM 응답 동안 시계가 멈춰 덜 걸리지만 없어지지는 않는다(main LLM 실행 L3: 허용 314 · 거절 353). 실행 앞 1/3 은 평가→Safety 가 0.05~0.27초라 대부분 허용되고, 총괄이 느려진 뒤 1/3 은 0.65~1.37초로 길어져 거절이 대부분이다. 숫자는 `B37_cross_runs.txt`.
