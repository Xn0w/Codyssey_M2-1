# 2026-10-11 최종 통합 시나리오 (거절 포함)

아래 ①·②는 노드 방식(당시 기본), ③은 도로 위 점 방식(10/11부터 기본)으로 돌린 결과다. UGV 코드는 모두 도로 AI 브랜치(`feat/ugv-road-ai`)를 AI 끄고 돌렸다. 이 브랜치(`feat/ugv-road-view`) 코드로 다시 돌린 결과는 ④.

`bash ugv/tools/run_twin_ugv.sh final`로 두 환경에서 돌린 기록입니다. ① 통합 시연 환경(총괄 테스트 저장소 + UGV, 공통 문서 5-1), ② 팀 main 총괄 + UGV(이 저장소 그대로, 관측 계획 없음). 팀 시연 시나리오(2019 인제 트윈, 배속 100, 도로 통제·혼잡 없음, AI 없음)에 운용자 거절 요청 1건을 더했습니다.

| 항목 | 값 |
|---|---|
| 요청 | `OPERATOR-REJECT:20_57` (칸 20_57, 38.06294, 128.13882), 종류 RECON, 자원 UGV, 시뮬레이션 3060초 |
| UGV 답 | A-ugv1·B-ugv1 모두 `REJECT TARGET_UNREACHABLE` — "가장 가까운 도로 노드가 2201 m 떨어짐 (허용 2000 m)" |
| 총괄 처리 | `TASK_HOLD NO_FEASIBLE_CANDIDATE` (소방차 2대는 `TYPE_NOT_ALLOWED`, UGV 2대는 `LOCAL_REJECT:TARGET_UNREACHABLE`) |
| 팀 main 총괄 (②) | 같은 칸·같은 결과. 시뮬레이션 4200초 요청 → A-ugv1·B-ugv1 `TARGET_UNREACHABLE` → `NO_FEASIBLE_CANDIDATE` 보류. 151초 동안 보류 32회, UGV 평가 64회. 팀 main 트윈은 불이 일찍 꺼져, 이 실행의 출동은 소방차 1회뿐(UGV 0회) |
| 재평가 | 보류 재개 조건 `NEW_RESOURCE_OR_INPUT` 때문에 환경 이벤트마다 다시 평가 — 실제 138초 동안 보류 27회, UGV 평가 39회, 모두 같은 거절 |

| 파일 | 내용 |
|---|---|
| `history_final_20261011T124401.jsonl` | UGV 실행 기록 (도로 상황판 다시 보기용, 거절 평가 39건 포함) |
| `orch_events_reject.json` | 총괄 장부에서 거절 요청(TASK-50520387b9d6)의 사건 148건만 뽑은 것 |
| `ugv_tasks_final.json` | UGV 서버 작업 상태 (실행 끝 시점) |
| `history_final_main_20261011T125624.jsonl` | ② 팀 main 총괄 실행의 UGV 기록 (다시 보기용) |
| `orch_events_reject_main.json` | ② 총괄 장부에서 거절 요청(TASK-dc6a514a8103) 사건 193건 |

화면: `ugv/ugv_image/orch_board_reject.png`(①), `orch_board_reject_main.png`(②) — 총괄 상황판 "정찰 · 20_57 보류 · 보낼 자원 없음". 도로 상황판 기록 탭 영상은 ②에서 찍은 [영상 09](https://drive.google.com/file/d/1gaAT6Zct-FrcqPuWq4ibnaslTJCdRTlK/view), GIF는 `docs/ugv/media/ugv_final_reject.gif`(30~90초 구간 3배속), 4컷은 `ugv_final_reject_frames.jpg`.

## ③ 설 자리 `road_point` + 총괄 2 km 시야 (조합, 2026-10-11 13:37)

통합 시연 환경에서 UGV 기본값을 `road_point`(도로 위 가장 가까운 점)로 바꿔 같은 `final`을 돌렸다. 총괄은 총괄 테스트 저장소 버전(시야 600 m~2 km + 지형 시선). 도로 위 점 정차와 2 km 시야를 처음으로 같이 돌린 것이다.

| 항목 | 노드 방식 (5-3 ⑥, `2026-10-11_twin4`) | 도로 위 점 (③) |
|---|---|---|
| 출동·도착 | 26회 출동, 모두 도착 | 출발 기록 17회, 도착 19회 (2회는 출발 기록 없이 바로 도착), 실패 0 |
| 평가 | 모두 ACCEPT | ACCEPT 122회(모두 설 지점 `stop_point` 포함), 거절 요청 건만 `TARGET_UNREACHABLE` 62회 |
| UGV 열화상 관측 | 26회 중 불 탐지 14회 (54 %) | 18회 중 불 탐지 12회 (67 %) |
| 목표 칸이 지형에 가림 | 6회 (23 %) | 3회 (17 %) |
| 선 자리 ↔ 목표 거리 | 중앙값 505 m, 평균 460 m, 최대 850 m | 중앙값 392 m, 평균 377 m, 최대 837 m |
| 거절 요청 | — | A-ugv1·B-ugv1 `TARGET_UNREACHABLE` → `NO_FEASIBLE_CANDIDATE` (①과 같음) |

- 도로 위 점에 서니 목표까지 거리가 중앙값으로 약 110 m 줄었고, 목표가 가리는 비율과 불을 놓치는 비율도 낮아졌다. 다만 불의 번짐·총괄 AI의 계획이 실행마다 달라 같은 조건의 반복 비교는 아니다 (각 1회).
- 거리는 총괄 관측 기록의 `position`(UGV가 선 자리)과 `target_point`(목표) 사이 직선거리다.

| 파일 | 내용 |
|---|---|
| `history_final_road_point_20261011T133724.jsonl` | ③의 UGV 실행 기록 (다시 보기용) |
| `ugv_tasks_final_road_point.json` | ③의 UGV 임무 상태 |
| `ugv_thermal_node_twin4.json`, `ugv_thermal_road_point.json` | 위 표의 열화상 관측만 뽑은 것 (총괄 장부 `observations`에서 UGV·THERMAL만) |
