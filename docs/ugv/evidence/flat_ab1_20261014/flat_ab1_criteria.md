# 평지 전체 월드 A→B 1회 — 사전 고정 기준 (2026-10-13 23:45, 실행 전 작성)

- 목적: S6 정적 연결(계획기 ACCEPT·route_check ok)이 실제 PX4+Gazebo 주행으로 이어지는지 처음 확인하는 스모크 1회.
- 월드: kangwon_flat (32×25 km 평면, ADAIR_wt_vehicle/ugv/gazebo/worlds). 지형·경사 없음.
- 차량: A-ugv1 (adair_ugv, 정식 모델, 후보 variant 없음), 출발 A 거점 출입 지점.
- 목표: B-ugv1 출입 지점 RP:683400513:2315.4 (17125.3, -5101.1). 계획기 정적 ETA 2959 s.
- 서버: ADAIR_wt_integ e839eee (S6 24c918e + STALE + 막힘 에피소드, Codex 2140 승격 동의). 부분집합 tiles_v2/road_subset_all_included.json (ab_eval 과 같음). E4·F1 플래그 off.
- 스크립트: logs/ugv/stage4/run_flat_ab.sh (run_sc_v6 사본, 평지용 사전 검사·증거 검사만 다름).

## 합격 (모두)
1. evaluate ACCEPT, execute 수락.
2. 임무 완료(도착) — 실패·중단·FAULT 없음.
3. 전복 없음 (road_test analysis rollover false).
4. 소요 ≤ 2 × 2959 s (벽시계, 실시간 배속 기준). 넘으면 원인 기록 후 불합격.

## 기록만 (판정 아님)
- 도로 중심 이탈 최대·분포, 회전별 이탈, 최고 속도, 도착 위치 오차, 교통·재계획 이벤트.

## 이 결과가 말하지 않는 것
- 지형 경사·S4/S5 게이트·소방차·운영 기본값. 평지 1회 통과는 그 증거가 아니다.
