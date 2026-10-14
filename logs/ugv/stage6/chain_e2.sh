#!/usr/bin/env bash
# 2026-10-13 경사 정지 최소 실험 E2 (F1 + F2(d) RA_ACC_RAD_MAX 3 — 차량 변형 susp_a_acc3). 단일 회차 — 9/18회 묶음 반복 아님.
#   조건: E1 과 같은 사례·서버(ADAIR_wt_integ_next 0a8a35a, UGV_STOP_CAP_FIRST=1) + 차량 변형 susp_a_acc3 (RA_ACC_RAD_MAX 3 만). F1+F2 증분 비교.
#   판정 기준 = docs/ugv/UGV_S4_경사_결과_20261013.md 'E2' 절 (결과 전 고정, 16:15) — ① acceptance_radius 3.0 발행·NAV_ACC_RAD 실제 3 ② F1 유지
#   ③ disarm 전 setpoint 0·Gazebo 연속 저속 (못 보면 '미확인') ④ 30 s 유지·재이동·yaw·경계 ⑤ 정지거리 ≤ 34.7 m ⑥ 주행 이탈 기록.
#   1차(15:53)는 단위 시험 중 파이썬 접근 위반(rc 139, test_route_verification GC 중) 으로 게이트 보류 → e2_hold1_crash139/ 보존, 같은 코드로 게이트부터 재실행.
cd "$(dirname "$0")/../../.."
M=$(pwd); RT=logs/ugv/stage4/run_sc_v6.sh; ST=$M/logs/ugv/stage5; SL=logs/ugv/stage6/slope; PY=../ADAIR/.venv/Scripts/python.exe
NX=../ADAIR_wt_integ_next; O=logs/ugv/stage6/e2; mkdir -p $O
(cd $NX && git rev-parse HEAD > ../ADAIR/$O/head.txt && PYTHONIOENCODING=utf-8 timeout 3000 $PY -m pytest -q -p no:cacheprovider -rf ugv/tests > ../ADAIR/$O/unit_tests.txt 2>&1; echo "rc=$?" >> ../ADAIR/$O/unit_tests.txt)
KNOWN="test_closed_loop_fault_redecision_other_resource_return_ready"
URC=$(grep -o "^rc=[0-9]*" $O/unit_tests.txt | tail -1 | cut -d= -f2)
OTHER=$(grep "^FAILED" $O/unit_tests.txt | grep -v "$KNOWN" | wc -l)
if [ "$URC" != 0 ] && { [ "$OTHER" -gt 0 ] || ! grep -q "^FAILED" $O/unit_tests.txt; }; then
  echo "CHAIN_E2_HOLD $(date) 단위 시험 실패(알려진 간헐 외 $OTHER 건 또는 수집 오류, rc=$URC)"; echo "CHAIN_E2_DONE $(date) (보류)"; exit 0
fi
SUB=$ST/tiles_v2/road_subset_all_included.json
export UGV_MODEL_VARIANT=susp_a_acc3 SERVER_TREE=ADAIR_wt_integ_next
E="UGV_STOP_CAP_FIRST=1 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
TAG=e2acc_s0547_downabort_a
T0=$(date -u +%H_%M)
env $E UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=wj495731_0574_0583 UGV_LAT_ACCEL=1.0 bash $RT $TAG $SL/s0547_down_spawn.txt $SL/s0547_down_fleet.json \
  bash -c "cd $NX && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $TAG --rid B-ugv1 --model adair_ugv_3 --target-node RP:683400547:165.9 --track-s 120 --post-stop-s 35 --world wj495731_0574_0583 --abort-after 2 --abort-on-downhill 0.03" > $O/run.out 2>&1
echo "run rc=$?" >> $O/run.out
# ULog: 차량 B-ugv1 = 인스턴스 px4-3 (MAV_SYS_ID 4) — ulog_last 포인터(px4-1) 결함을 피해 인스턴스 폴더에서 이 회차 시각 뒤 최신 파일
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-3/log/*/*.ulg | head -1" > $O/ulog_px4-3.txt 2>&1
echo "CHAIN_E2_DONE $(date) $(tail -1 $O/run.out) ulog=$(cat $O/ulog_px4-3.txt)"
