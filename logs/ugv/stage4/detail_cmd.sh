#!/usr/bin/env bash
# run_sc_v4 가 서버 준비 뒤 실행: (WSL) gz_detail 상세 기록 백그라운드 + (Windows) wt_fix road_test. 환경 D_* 는 체인이 준다.
#   D_TAG D_WORLD D_MODEL(adair_ugv_N) D_RID D_TARGET D_TILES(절대) D_SUB(절대)
cd "$(dirname "$0")/../../.."
V=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle
R=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --cd "$V" --exec env GZ_PARTITION=adair_ugv GZ_IP=127.0.0.1 python3 -m ugv.tools.gz_detail --world "$D_WORLD" --model "$D_MODEL" --out "$R/logs/ugv/stage6/jcross/${D_TAG}_detail.csv" --duration 170 > "logs/ugv/stage6/jcross/${D_TAG}_detail.log" 2>&1 &
REC=$!
sleep 2
( cd ../ADAIR_wt_fix && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET="$D_SUB" ADAIR_TILES_OUT="$D_TILES" ../ADAIR/.venv/Scripts/python.exe -m ugv.tools.road_test --tag "$D_TAG" --rid "$D_RID" --model "$D_MODEL" --target-node "$D_TARGET" --track-s 120 --post-stop-s 15 --world "$D_WORLD" )
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- pkill -TERM -f "ugv.tools.gz_detail --world $D_WORLD"
wait $REC 2>/dev/null
