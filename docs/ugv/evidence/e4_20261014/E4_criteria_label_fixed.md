# E4 Gazebo 4회 — 사전 고정 기준 (2026-10-14, 실행 전 작성 — 시각 표기 정정: 최종 수정 01:04:10, E4-1 시작 01:06:45)

근거: `docs/ugv/UGV_미해결6건_페이블해결안_20261013.md` 1.5 (E4) + 2.2·2.3 (E2 ③ 관측 훅), Codex 2140·2315·2350, 리더 전달 의견(2026-10-14 00:45: 서비스 목적지 오차·PX4 자체 정지·disarm 전 정지 유지·이후 30 s 밀림 기록, E2 경계 판정 보존).

## 구성 (고정)
- 서버 ADAIR_wt_hook `17a7305` (= e839eee + E4 b506923 + E2 ③ 시험 훅). 스크립트 `run_sc_v7.sh` (단계별 rc, TAG 재사용 거부).
- 플래그: `UGV_PX4_END_EXTEND=1`, `UGV_PX4_PARK_AFTER_S=2.0` (서버는 run_sc 가 UGV_TEST_HOOKS=1), 다른 후보 0 (`UGV_STOP_CAP_FIRST=0 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0`), `UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1`, `UGV_LAT_ACCEL=1.0` (E3 와 같음).
- 선행 게이트: 같은 트리 전체 단위시험 통과 (접근 위반으로 중단되면 새 run id 로 1회 재실행, 실패 시험이 있으면 E4 보류).

| 회차 | TAG | 차량 변형 | 사례 | 기대 |
|---|---|---|---|---|
| E4-1 | e4_acc3_s1096_a | susp_a_acc3 | s1096_down 곡선 도착 (B-ugv1, wj495663_1400_0021, RP:683501096:10.0) | 연장 3.0 적용 |
| E4-2 | e4_acc3_s1096_b | susp_a_acc3 | 같음 | 연장 3.0 적용 |
| E4-3 | e4_raoff_s1096_a | susp_a (RA −1) | 같음, 플래그 on | 게이트 거절 (offset 0), 훅도 무시 (park after 1.0) |
| E4-4 | e4_acc3_s3113_a | susp_a_acc3 | s3113_down 직선 3~4 % 내리막 도착 (A-ugv1, wj494846_1237_1921, RP:682503113:143.0) | 연장 적용 |

## 회차 판정 (모두 충족해야 회차 통과)
1. 증거: `END_EXTENSION`(E4-1·2·4) / `END_EXTENSION_SKIPPED reason OFFSET_0`(E4-3) 이 게이트대로, `/state driver_evidence` 의 NAV_ACC_RAD·RA_ACC_RAD_MAX·park_policy 가 차량 변형과 일치 (acc3: after_s 2.0 test_hook true / RA −1: after_s 1.0 test_hook false).
2. 서비스 목적지 오차: 최종 정지 위치(Gazebo) ↔ plan.dest ≤ 1.0 m (E3 기준값 base 0.43 / acc 3.16). E4-3 은 ≈ E3 base (≤ 1.0 m).
3. ULog seq_reached 빠짐 0.
4. judge3 (slope_report v2): 도착·차체 도로 경계 안·정지 확인, outside_max 가 E3 같은 사례 ±0.3 m (E4-1~3: E3 −2.48/−2.45 기준).
5. 정지 뒤 30 s 수평 이동 ≤ 0.1 m (hold v2).
6. PX4 자체 정지 (acc3 회차만): `mission_result.finished` 뒤 0.1 s 안 `rover_speed_setpoint.speed_body_x = 0` (③a).
7. E2 ③ 분리 (훅 회차): ③b Gazebo < 0.2 m/s 를 finished + 1.5 s 안·disarm 전 도달, ③c 그 뒤 < 0.2 m/s 연속 ≥ 1.0 s 가 disarm 전에 끝남, ③d disarm − ③b ∈ [after_s, after_s + 0.6] 이고 last_error 에 '상한' 없음, ③e RUNAWAY·cut_drive 미사용. E4-3 (훅 무시)은 ③d 를 after_s 1.0 으로 본다.
8. ARRIVED `to_dest_m ≤ 1.0`.

## 묶음 판정
- 4/4 회차 통과 → F2(RA_ACC_RAD_MAX 3) + 연장을 **한 짝으로 채택 후보** (운영 기본값 아님, Codex 검토).
- 하나라도 실패 → 둘 다 채택 안 함, 추가 회차 없이 원인 분석 (평균·다수결 없음).
- 래퍼 무효(증거·사후 정지·오염·접근 위반)는 판정 회차가 아니다 — 새 TAG 로 1회만 다시. 같은 무효 2회면 중단·보고.
- 이 결과는 경사 정지(F1) 효과, S4/S5 게이트, 소방차 증거가 아니다.

### 보정 (E4-1 시작 전, 파일 mtime 01:04:10 — '01:12' 는 잘못된 추정 표기. 판정기 E3 기록 검증 중 발견)
- 7 (E2 ③b~e) 는 PX4 가 끝 지점에서 스스로 서는 차(acc3: E4-1·2·4)에만 적용. E4-3 (RA −1) 은 PX4 정지 분기가 없어 LOITER 크롤 → E3 base 기록에서 disarm 이 finished + 4.0 s (RUNAWAY 상한 경로)라 ③ 이 구조적으로 정의되지 않음 → **기록만** (Fable 1.5 ⑥ 도 acc3 의미). E4-3 판정 = 1·2·3·4·5·8.
- 7e 판정 근거: 서버 로그에 driver last_error 가 남지 않아, ULog disarm − finished ≥ 3.9 s 이고 그때 Gazebo 속도 ≥ 0.3 m/s 이면 RUNAWAY 로 본다.
- 3 (seq_reached 빠짐): ULog mission_result 는 기록 주기로 솎여 E3 두 회차 모두 홀수 seq 만 남음 → ULog 로는 '빠짐 0' 을 판정할 수 없다. 판정 = 마지막 도달 seq = seq_total − 1 이고 되돌아감 없음, 빠져 보이는 목록은 기록.
- Gazebo 속도 = 0.2 s 창 위치 차분 (CSV 0.01 m 반올림 잡음 회피, slope_report 와 같은 창).
