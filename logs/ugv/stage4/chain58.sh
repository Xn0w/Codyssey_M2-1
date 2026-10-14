#!/usr/bin/env bash
# 2026-10-12 차량 개조 P2 3.6: j494943 교차 비교 — base(원본+접촉 센서) vs susp_a(서스펜션, 관절 발행) × D5·D8 × 3 = 12, ABBA 순서(회차마다 역순).
# 상세 기록 gz_detail(접촉 상태·법선력·서스펜션 관절) 동시. 설정 = chain57 과 같음 (PASS_SKIP=0 STALL_DETECT=0 LAT_ACCEL 1.0 track-s 120 post-stop 15, 서버 wt_turn 30457e7, 도구 wt_fix 5ffb41a)
cd "$(dirname "$0")/../../.."
M=$(pwd); RT=logs/ugv/stage4/run_sc_v4.sh; ST=$M/logs/ugv/stage5; J=logs/ugv/stage5/jturn
until grep -q CHAIN57_DONE logs/ugv/stage4/chain57.out 2>/dev/null; do sleep 15; done
export D_SUB=$ST/tiles_v2/road_subset_all_included.json D_WORLD=wj494943_1351_1352 D_MODEL=adair_ugv_1 D_RID=A-ugv1 D_TARGET=RP:682501352:20.0
run() {  # 후보 지면 타일 회차
  export D_TAG="c58_j494943_$2_$1_$4" D_TILES=$ST/$3
  UGV_MODEL_VARIANT=$1 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=0 PF_SKIP_SUBSET=1 SUBSET=$D_SUB TILES=$3 WORLD=$D_WORLD UGV_LAT_ACCEL=1.0     bash $RT "$D_TAG" $J/j494943_1351_1352_$2_spawn.txt $J/j494943_1351_1352_fleet.json bash logs/ugv/stage4/detail_cmd.sh
}
run base D5 tiles_v2_D5all a
run susp_a D5 tiles_v2_D5all a
run susp_a D8 tiles_v2_D8all a
run base D8 tiles_v2_D8all a
run base D8 tiles_v2_D8all b
run susp_a D8 tiles_v2_D8all b
run susp_a D5 tiles_v2_D5all b
run base D5 tiles_v2_D5all b
run base D5 tiles_v2_D5all c
run susp_a D5 tiles_v2_D5all c
run susp_a D8 tiles_v2_D8all c
run base D8 tiles_v2_D8all c
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN58_DONE $(date)"
