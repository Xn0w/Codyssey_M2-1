#!/usr/bin/env bash
# 2026-10-13 경사 정지 후보 검증 (추가 보완 4). chain_ft4b(fire_v2b 마무리) 뒤에. 통합 트리 ADAIR_wt_integ 서버 (정체 감지 켬).
#  0) sim 시간대: 통합 트리 전체 단위 시험 (후보 기본 off — 기본 동작 불변 확인), 회차 원문·rc 보존
#  1) 대조: 후보 off, 5~6 % 하강 중단 3회 (트리 차이만)
#  2) 후보 on (UGV_STOP_SPEED_CMD=1 UGV_STOP_GRADE=1 UGV_TERRAIN_TILES=tiles_v2): 5~6 % 하강 중단 3회, 3~4 % 하강 중단 3회
# 판정 = slope_report v2 (하강 제동 정규화 지표·구간 분리). 결과 전 운영 가능 선언 금지. 실패도 그대로 보고.
cd "$(dirname "$0")/../../.."
until grep -q CHAIN_FT4B_DONE logs/ugv/stage6/chain_ft4b.out 2>/dev/null; do sleep 30; done
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v6.sh; ST=$M/logs/ugv/stage5; SL=logs/ugv/stage6/slope
(cd ../ADAIR_wt_integ && git rev-parse HEAD > $M/logs/ugv/stage6/slope3_integ_head.txt && PYTHONIOENCODING=utf-8 timeout 3000 $PY -m pytest -q -p no:cacheprovider -rf ugv/tests > $M/logs/ugv/stage6/slope3_unit_tests.txt 2>&1; echo "rc=$?" >> $M/logs/ugv/stage6/slope3_unit_tests.txt)
# 기동 게이트 (Codex 검토): 단위 시험 실패가 알려진 간헐 항목만이면 진행, 그 밖의 실패·rc 이상이면 보류. DONE 은 성공 아님
KNOWN="test_closed_loop_fault_redecision_other_resource_return_ready"
URC=$(grep -o "^rc=[0-9]*" logs/ugv/stage6/slope3_unit_tests.txt | tail -1 | cut -d= -f2)
OTHER=$(grep "^FAILED" logs/ugv/stage6/slope3_unit_tests.txt | grep -v "$KNOWN" | wc -l)
if [ "$URC" != 0 ] && { [ "$OTHER" -gt 0 ] || ! grep -q "^FAILED" logs/ugv/stage6/slope3_unit_tests.txt; }; then
  echo "CHAIN_SLOPE3_HOLD $(date) 단위 시험 실패(알려진 간헐 외 $OTHER 건 또는 수집 오류, rc=$URC) — 주행 보류"; echo "CHAIN_SLOPE3_DONE $(date) (보류)"; exit 0
fi
SUB=$ST/tiles_v2/road_subset_all_included.json
export UGV_MODEL_VARIANT=susp_a SERVER_TREE=ADAIR_wt_integ
run() {   # tag case world rid inst target extra_env
  env $7 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $SL/$2_spawn.txt $SL/$2_fleet.json \
    bash -c "cd ../ADAIR_wt_integ && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $1 --rid $4 --model adair_ugv_$5 --target-node $6 --track-s 120 --post-stop-s 35 --world $3 --abort-after 2 --abort-on-downhill 0.03"
}
# 비교 밖 후보는 명시적으로 고정 (Codex 검토). ON 은 속도 상한 명령 + 경사 정지 모델 '묶음' 효과 — 단독 효과로 주장하지 않는다
ON="UGV_STOP_SPEED_CMD=1 UGV_STOP_GRADE=1 UGV_SPEED_TERRAIN=0 UGV_TERRAIN_TILES=$ST/tiles_v2"
OFF="UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0"
for rep in a b c; do
  run cs3off_s0547_downabort_$rep s0547_down wj495731_0574_0583 B-ugv1 3 RP:683400547:165.9 "$OFF"
  run cs3on_s0547_downabort_$rep s0547_down wj495731_0574_0583 B-ugv1 3 RP:683400547:165.9 "$ON"
  run cs3on_s3113_downabort_$rep s3113_down wj494846_1237_1921 A-ugv1 1 RP:682503113:143.0 "$ON"
done > logs/ugv/stage6/slope3_runs.out 2>&1
echo "CHAIN_SLOPE3_DONE $(date) unit_tests=$(tail -1 logs/ugv/stage6/slope3_unit_tests.txt)"
