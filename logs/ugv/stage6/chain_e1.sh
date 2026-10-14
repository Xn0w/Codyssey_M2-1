#!/usr/bin/env bash
# 2026-10-13 경사 정지 최소 실험 E1 (Fable 원인 검토 F1, 오퍼스 소스 대조). 단일 회차 — 9/18회 묶음 반복 아님.
#   조건: chain_slope3 OFF 와 같은 사례(s0547 5.5 % 내리막 중단) + UGV_STOP_CAP_FIRST=1 만 켬 (STOP_SPEED_CMD·STOP_GRADE·SPEED_TERRAIN(_CMD) 0).
#   서버 트리 ADAIR_wt_integ_next 0a8a35a (통합 트리는 chain_simint2 가 쓰는 중이라 건드리지 않음).
#   판정 기준 (결과 전 고정, docs/ugv/UGV_S4_경사_결과_20261013.md 'E1' 절): ① px4-3 ULog 새 mission_id 첫 position_setpoint_triplet
#   cruising_speed = 명령값(±0.05) ② 명령 뒤 Gazebo 최고 속도 ≤ 명령 시 속도 + 0.5 ③ 명령 → 감속 시작 ≤ 1.0 s ④ Gazebo 정지거리 < 48.9 m
#   (OFF 최소) ⑤ 도로 경계 안·정지 뒤 재이동 없음 ⑥ mission finished 와 실제 정지 시각 차 기록 (disarm 의존 여부 — 판정 아님).
cd "$(dirname "$0")/../../.."
M=$(pwd); RT=logs/ugv/stage4/run_sc_v6.sh; ST=$M/logs/ugv/stage5; SL=logs/ugv/stage6/slope; PY=../ADAIR/.venv/Scripts/python.exe
NX=../ADAIR_wt_integ_next; O=logs/ugv/stage6/e1; mkdir -p $O
(cd $NX && git rev-parse HEAD > ../ADAIR/$O/head.txt && PYTHONIOENCODING=utf-8 timeout 3000 $PY -m pytest -q -p no:cacheprovider -rf ugv/tests > ../ADAIR/$O/unit_tests.txt 2>&1; echo "rc=$?" >> ../ADAIR/$O/unit_tests.txt)
KNOWN="test_closed_loop_fault_redecision_other_resource_return_ready"
URC=$(grep -o "^rc=[0-9]*" $O/unit_tests.txt | tail -1 | cut -d= -f2)
OTHER=$(grep "^FAILED" $O/unit_tests.txt | grep -v "$KNOWN" | wc -l)
if [ "$URC" != 0 ] && { [ "$OTHER" -gt 0 ] || ! grep -q "^FAILED" $O/unit_tests.txt; }; then
  echo "CHAIN_E1_HOLD $(date) 단위 시험 실패(알려진 간헐 외 $OTHER 건 또는 수집 오류, rc=$URC)"; echo "CHAIN_E1_DONE $(date) (보류)"; exit 0
fi
SUB=$ST/tiles_v2/road_subset_all_included.json
export UGV_MODEL_VARIANT=susp_a SERVER_TREE=ADAIR_wt_integ_next
E="UGV_STOP_CAP_FIRST=1 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
TAG=e1cap_s0547_downabort_a
T0=$(date -u +%H_%M)
env $E UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=wj495731_0574_0583 UGV_LAT_ACCEL=1.0 bash $RT $TAG $SL/s0547_down_spawn.txt $SL/s0547_down_fleet.json \
  bash -c "cd $NX && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $TAG --rid B-ugv1 --model adair_ugv_3 --target-node RP:683400547:165.9 --track-s 120 --post-stop-s 35 --world wj495731_0574_0583 --abort-after 2 --abort-on-downhill 0.03" > $O/run.out 2>&1
echo "run rc=$?" >> $O/run.out
# ULog: 차량 B-ugv1 = 인스턴스 px4-3 (MAV_SYS_ID 4) — ulog_last 포인터(px4-1) 결함을 피해 인스턴스 폴더에서 이 회차 시각 뒤 최신 파일
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-3/log/*/*.ulg | head -1" > $O/ulog_px4-3.txt 2>&1
echo "CHAIN_E1_DONE $(date) $(tail -1 $O/run.out) ulog=$(cat $O/ulog_px4-3.txt)"
