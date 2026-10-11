# 2026-10-11 이 브랜치(`feat/ugv-road-view`) 코드로 다시 확인

도로 AI 브랜치 코드로 얻은 근거(⑥~⑧)를 이 브랜치 코드(도로 AI 없음, 4대, 설 자리 기본 `road_point`)로 다시 확인한 기록이다.

**자동시험·경우별 재현** — `pytest_and_cases.txt`: 자동시험 5개 통과, 경우별 재현 18건 모두 기대대로 (10/10 숫자와 같음).

**통합 시험 `final`** — 통합 시연 환경(총괄 테스트 저장소 총괄·환경 + 이 브랜치 UGV 코드), `bash ugv/tools/run_twin_ugv.sh final`, 배속 100, 시뮬레이션 약 3시간.

| 항목 | 값 |
|---|---|
| 도착 | 23회 (A-ugv1 6, B-ugv1 16, A-fire1 1), 실패 0. 출발 기록은 18회 — 나머지는 차가 이미 설 지점 근처라 출발 기록 없이 도착 |
| 평가 | ACCEPT 137회(모두 설 지점 `stop_point` 포함), 거절 요청 건만 `TARGET_UNREACHABLE` 91회 |
| UGV 열화상 관측 (총괄 모의) | 22회 중 불 탐지 18회 (82 %), 목표 칸이 지형에 가림 2회 (9 %) |
| 선 자리 ↔ 목표 거리 | 중앙값 301 m, 평균 359 m, 최대 837 m |
| 거절 요청 | 칸 20_57(도로에서 2.20 km) → A-ugv1·B-ugv1 `TARGET_UNREACHABLE` → `NO_FEASIBLE_CANDIDATE` 보류, 출동 없음. 이후 환경 이벤트마다 다시 평가(보류 53회) |

| 파일 | 내용 |
|---|---|
| `pytest_and_cases.txt` | 자동시험·경우별 재현 결과 |
| `history_road_view_final_20261011T135756.jsonl` | UGV 실행 기록 (다시 보기용) |
| `ugv_tasks_road_view_final.json` | UGV 임무 상태 |
| `ugv_thermal_road_view.json` | 총괄 장부에서 UGV 열화상 관측만 뽑은 것 |
| `orch_events_reject_road_view.json` | 총괄 장부에서 거절 요청(TASK-5dcbbe2f8b06) 사건만 뽑은 것 |

열화상·거리 숫자는 불 번짐과 총괄 AI 계획이 실행마다 달라 1회 값이다. 노드 방식 결과(`2026-10-11_twin4`, 54 %·505 m)와는 경향만 비교한다.
