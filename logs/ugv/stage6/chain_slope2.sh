#!/usr/bin/env bash
# 2026-10-13 후속 계획 S4 7.3 남은 경사 조건 — 횡경사 회전 (UGV susp_a, 서버 ADAIR_wt_fix 정체 감지 켬, tiles_v2 실제 지형). 3사례 × 3회.
# 후보 = find_slope2.py (결과 전 기준), 사례 = make_slope_cases.py slope2. 종단 전이 후보(682503070)는 양방향 계획 거절 → 미검증으로 기록 (기준 완화 안 함).
# 래퍼 run_sc_v6. chain_ft4 뒤에 (끝 또는 거부 표식).
cd "$(dirname "$0")/../../.."
until grep -qE "CHAIN_FT4_DONE|CHAIN_FT4_REFUSED" logs/ugv/stage6/chain_ft4.out 2>/dev/null; do sleep 30; done
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v6.sh; ST=$M/logs/ugv/stage5; SL=logs/ugv/stage6/slope2
SUB=$ST/tiles_v2/road_subset_all_included.json
export UGV_MODEL_VARIANT=susp_a SERVER_TREE=ADAIR_wt_fix
run() {   # tag case world rid inst target
  UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $SL/$2_spawn.txt $SL/$2_fleet.json \
    bash -c "cd ../ADAIR_wt_fix && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $1 --rid $4 --model adair_ugv_$5 --target-node $6 --track-s 150 --post-stop-s 35 --world $3"
}
for rep in a b c; do   # 목표 = slope2/cases.json
  run cx_s1592_down_$rep s1592_down wj494866_0722_1925 A-ugv1 1 RP:682501592:84.2
  run cx_s1096_up_$rep s1096_up wj495663_1400_0021 B-ugv1 3 RP:683501096:256.0
  run cx_s1096_down_$rep s1096_down wj495663_1400_0021 B-ugv1 3 RP:683501096:10.0
done > logs/ugv/stage6/slope2_runs.out 2>&1
echo "CHAIN_SLOPE2_DONE $(date)"
