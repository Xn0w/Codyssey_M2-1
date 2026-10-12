# 통합 시험 근거 (2026-10-12)

통합·관제 파트 문서 [`ADAIR_통합관제_파트정리_발표범위.md`](../../../common/ADAIR_통합관제_파트정리_발표범위.md) 7장의 근거 파일입니다.

## 조건

| 항목 | 내용 |
|---|---|
| 기준 코드 | `main` `ca19f2c` (PR #42 — UGV #39, 환경 #41 반영) |
| 환경 | Windows 11, Python 3.11, 모든 서버 로컬 실행 |
| 실행 | `python run_servers.py start --twin` (2019 인제 트윈, 시계 100배속) |
| 자원 | UAV mock 2대(A-uav1·A-uav2), UGV sim 4대(A-ugv1·A-fire1·B-ugv1·B-fire1) |
| 담당 | 이원규 (통합·관제·로그) |

## 파일

| 파일 | 만든 방법 | 확인할 내용 |
|---|---|---|
| `servers_status.txt` | 트윈 실행 중 `python run_servers.py status` | 9개 서버(env·uav1·uav2·ugv·orch·web·clock·operator·dispatch) 상태 |
| `board_snapshot.json` | 트윈 시작 약 4분 뒤 `GET http://127.0.0.1:8200/priority/board` | 총괄이 아는 불(`known.fires`), 임무 순서(`auto_order`), 정찰·측정 결과(`results`), 보류 사유 |
| `dispatch.log` | `logs/servers/dispatch.log` 복사 | 불 확인 뒤 "남전1리 마을회관 지상 지원" 요청과 총괄 응답(HTTP 202). 여러 번 실행한 기록이 이어져 있음 |
| `pytest_orchestrator.txt` | 트윈 종료 후 `python -m pytest -q orchestrator` | 총괄 시험 전체 결과 |
| `integration_checks.txt` | `tests.it_cases`, `tests.int01`~`int04_05`, `tests.log_coverage_check` 순서대로 실행 | IT-01·02, INT-01(출동 총괄 경유), INT-02(진화 미반영), INT-03(총괄 판단 패널), 로그 기록, INT-04·05(거점 좌표·시계 하나·트윈 구성) |

## 참고

- 관측값은 모두 모의 값(`SIMULATED`)입니다. 실제 센서 측정이 아닙니다.
- 이 실행에서도 환경 서버의 불은 발화점 1칸에서 번지지 않았습니다(알려진 한계, 환경 담당 확인 중).
- 화면·영상은 [`../../media/`](../../media/)에 있습니다.
