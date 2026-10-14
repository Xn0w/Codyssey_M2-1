# 2026-10-12 `thermal` 구성 — UGV 마을회관·휴게소 방어 출동 + UGV 열화상 (2 km 지형 시선)

실행: `bash ugv/tools/run_twin_ugv.sh thermal` (팀 main `872dcd1` + 이 브랜치, 2019 인제 트윈, 배속 100, macOS)

- 마을회관·휴게소 방어 출동: 통합 담당의 `tools/twin_ground_dispatch.py`를 `--types UGV --site NAMJEON1_HALL,INJE_REST_AREA`로 실행 (소방차 대신 UGV)
- UGV 열화상 요청: `ugv/tools/twin_thermal_request.py --auto` (시뮬레이션 20분부터 30분마다)
- 두 도구 모두 총괄 공식 API(`POST /tasks`)로 요청만 하고, 어느 UGV를 보낼지·갈 수 있는지·관측 판정은 총괄과 UGV가 정한다

| 임무 | 요청 | 총괄 배정 | 결과 |
|---|---|---|---|
| 열화상 정찰 (칸 13_101, 불타는 중) | 시뮬레이션 35분, UGV 전용 | A-ugv1 수락, ETA 352초, 목표에서 80 m 도로 위 정차 | 지형 시선 관측(`ASSUMED_GROUND_LOS_V1`): 반경 2 km 안 321칸 보임·984칸 지형에 가림, 불 탐지, 목표 칸 봄 → 완료 |
| 남전1리 마을회관 방어 (칸 24_116) | 불 확인 뒤 (0.58 h) | B-ugv1 수락, ETA 1,758초 | 도착 → 완료 |
| 인제휴게소 방어 (칸 28_91) | 불 확인 뒤 (0.58 h) | 처음엔 UGV 2대 모두 다른 임무 중(`OCCUPIED`) → 보류 2회 → A-ugv1이 열화상 정찰을 끝낸 뒤 수락, ETA 118초 | 도착 → 완료 |

- 신고 때 자동 정찰(UAV·UGV 허용)은 더 가까운 드론(A-uav1)이 맡았다
- 팀 main 트윈은 불이 한 칸에서 꺼져(불 칸 1개) 열화상 요청은 1건만 나갔다 (이후 "도로 1.9 km 안에 새 불 칸 없음")
- 마을회관·휴게소 방어는 센서 없는 지상 지원(`GROUND_SUPPORT`)이라 도착으로 완료되고, 열화상·지형 관측은 하지 않는다
- 근거: `logs/twin/20261012_202027/orchestrator.sqlite3` (`tasks`·`events`·`observations`), `logs/twin_thermal_request.log`, `logs/servers/dispatch.log` (로컬 실행 기록, 저장소에 넣지 않음)
