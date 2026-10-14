#!/usr/bin/env bash
# 2026-10-13 후속 계획 S4 7.3 / 차량 개조 계획 T6 경사 (UGV susp_a, 서버 ADAIR_wt_fix 정체 감지 켬, 실제 지형 tiles_v2).
# 사례 = make_slope_cases.py (682503113 3~4 %, 683400547 5~6 %; 682502940 은 경사 불균일로 제외). 조건 × 3회:
#   up / down       : 도착 (등판 속도 유지·하강 도착 정지) + 도착 뒤 35 s 관측 (정지 유지 밀림 ≤ 0.1 m/30 s)
#   down_abort      : 내리막 8 m/s 넘을 때 임무 중단 (--abort-on-downhill 0.03) → 하강 제동 (평지 × 1.3 이내)
# 판정 기준은 차량 개조 계획 T6 (결과 전 고정). 래퍼 run_sc_v6 (v5 + wsl --exec, 사전·사후 정지·증거 검사). chain_ft3 뒤에.
cd "$(dirname "$0")/../../.."
until grep -q CHAIN_FT3_DONE logs/ugv/stage6/chain_ft3.out 2>/dev/null; do sleep 30; done
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v6.sh; ST=$M/logs/ugv/stage5; SL=logs/ugv/stage6/slope
SUB=$ST/tiles_v2/road_subset_all_included.json
export UGV_MODEL_VARIANT=susp_a SERVER_TREE=ADAIR_wt_fix
run() {   # tag case world rid inst target extra
  UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $SL/$2_spawn.txt $SL/$2_fleet.json \
    bash -c "cd ../ADAIR_wt_fix && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $1 --rid $4 --model adair_ugv_$5 --target-node $6 --track-s 120 --post-stop-s 35 --world $3 $7"
}
for rep in a b c; do   # 목표 = slope/cases.json
  run cs_s3113_up_$rep s3113_up wj494846_1237_1921 A-ugv1 1 RP:682503113:25.0 ""
  run cs_s3113_down_$rep s3113_down wj494846_1237_1921 A-ugv1 1 RP:682503113:143.0 ""
  run cs_s3113_downabort_$rep s3113_down wj494846_1237_1921 A-ugv1 1 RP:682503113:143.0 "--abort-after 2 --abort-on-downhill 0.03"
  run cs_s0547_up_$rep s0547_up wj495731_0574_0583 B-ugv1 3 RP:683400547:10.0 ""
  run cs_s0547_down_$rep s0547_down wj495731_0574_0583 B-ugv1 3 RP:683400547:165.9 ""
  run cs_s0547_downabort_$rep s0547_down wj495731_0574_0583 B-ugv1 3 RP:683400547:165.9 "--abort-after 2 --abort-on-downhill 0.03"
done > logs/ugv/stage6/slope_runs.out 2>&1
echo "CHAIN_SLOPE_DONE $(date)"
