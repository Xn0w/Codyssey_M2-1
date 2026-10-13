# 진단 6 — EKF 정지 속도 넘침 A/B (Codex 0455 2·3절) — 사전 고정 (2026-10-14 04:47:44, 실행 전)

**진단이며 채택 검증이 아니다.** v5 의 5/6 PASS·채택 보류, s0547 c FAIL 은 그대로. A/B 한 쌍으로 인과·안정성을 확정하지 않는다.
고정: 서버 ADAIR_wt_hook `03d5b5d` (= b9fe46b + park 표본 계측, 시험 훅 전용), 판정기 diag6/slope5_judge.py (= v5 판정기, 경로만), run_sc_v8, 선행 전체 단위시험 suite_parksamples 통과.

## A (먼저 1회): v5 조건 그대로 + 계측 — 태그 d6_on_s0547_downabort_A
ON = UGV_STOP_CAP_FIRST=1 UGV_STOP_ITEMS_RAMP=1 UGV_PX4_PARK_AFTER_S=2.0, END_EXTEND 0, 다른 후보 0, susp_a_acc3, s0547 하강 중단 (B-ugv1, wj495731_0574_0583, RP:683400547:165.9, --track-s 200 --post-stop-s 50).
비교 허용 (v5 s0547 a/b/c 범위 기준): 명령 때 속도 9.2~9.5 m/s, needed 33.5~35.5 m, 경사 트리거 −5 ~ −6 %. 밖이면 비교 무효로 표시. 난수 시드: Gazebo·PX4 SITL 시드 고정 수단 없음 — 한계로 기록.
A 뒤 자동 진행 없음: 기록·안전 상태(FAULT/CUT·물리 이동·무효)와 park 표본·EKF·groundtruth 를 먼저 읽고 B 진행 여부를 정한다.

## B (A 뒤, 별도 고정): 말단 구간 감속 프로필만 변경 1회 — 후보 값은 Fable 보충 검토와 운동학 검토 뒤 결과 전에 고정.

## 지표 (A·B 같은 구간·같은 정의)
경계 진입 실제 속도·실제 감속(ULog groundtruth 차분)·jerk, 물리 정지 뒤 EKF 진행 방향 부호 속도의 음 최소·양 넘침 최대·0 교차 시각, EKF 위치 이동 (fin+1~disarm), GNSS 속도 최대, park 표본 열 (vN·vE·나이·still_since), 실제 park 분기·저속 연속 창, 정지거리·감독 여유·30 s 유지 (v5 판정기 그대로). 반등이 park 창 밖으로 옮겨 PASS 한 것은 추정 품질 개선과 구분해 보고.
