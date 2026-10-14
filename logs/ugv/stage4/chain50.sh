#!/usr/bin/env bash
# 2026-10-12 실행 지시서 1단계 6번 회귀 (wt_fix, 정체 감지 ON·건너뛰기 OFF·직선 정지 기본): v2 통합 경로 A (tz_a33v2)
# (1) 정상 왕복 (2) 주행 중 취소 (3) 주행 중 새 목표 (4) 통신 단절(서버의 이 차량 MAVSDK 연결만 끊기, 경로 45 % 지점) — 모두 정지 뒤 관측
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; ST=$M/logs/ugv/stage5; RT=logs/ugv/stage4/run_sc_fix.sh
SUB=$ST/tiles_v2/road_subset_tz_a33v2.json; SP=logs/ugv/stage4/tz_a33v2_spawn_ugv.txt; FL=logs/ugv/stage4/single_a_fleet.json
run() {  # tag 나머지=road_test 인자
  t=$1; shift
  UGV_PX4_STALL_DETECT=1 UGV_PX4_PASS_SKIP=0 SUBSET=$SUB TILES=tiles_v2 WORLD=tz_a33v2 UGV_LAT_ACCEL=1.0 bash $RT $t $SP $FL bash -c "cd ../ADAIR_wt_fix && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB $PY -m ugv.tools.road_test --tag $t --rid A-ugv1 --model adair_ugv_1 --world tz_a33v2 $*"
}
run c50_integ_round --target-node RP:682501105:65.5 --return-home --track-s 420 --post-stop-s 15
run c50_integ_abort --target-node RP:682501105:65.5 --abort-after 25 --track-s 200 --post-stop-s 15
run c50_integ_second --target-node RP:682501105:65.5 --second 38.05757417 128.16602132 --second-after 25 --track-s 400 --post-stop-s 15
UGV_PX4_STALL_DETECT=1 UGV_PX4_PASS_SKIP=0 SUBSET=$SUB TILES=tiles_v2 WORLD=tz_a33v2 UGV_LAT_ACCEL=1.0 bash $RT c50_link_hook $SP $FL bash -c "cd ../ADAIR_wt_fix && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB $PY -m ugv.tools.link_loss_compare run --tag c50_link_hook --target-node RP:682501105:65.5 --cut hook --cut-xy 4056.9 5877.5 --observe 90 --rid A-ugv1 --instance 1 --model adair_ugv_1 --world tz_a33v2"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN50_DONE $(date)"
