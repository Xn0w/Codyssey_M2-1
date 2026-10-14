#!/usr/bin/env bash
# A 단계 시험 명령 (run_sc_v11_c1 가 ADAIR 루트에서 실행): 고율 바퀴/접촉/서스펜션 기록기 (WSL, 파티션 adair_ugv) 를 띄운 뒤 road_test (원 B 와 같은 인자).
T=$1; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR; O=logs/ugv/stage6/terrain_ab/envB_c1
M=$(pwd); ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe; HK=../ADAIR_wt_hook; SUB=$ST/tiles_v2/road_subset_ab_route_v1.json
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "export GZ_PARTITION=adair_ugv GZ_IP=127.0.0.1; (setsid nohup python3 $W/logs/ugv/stage6/terrain_ab/seamR/gz_detail_seam.py --world ab_route_v1 --model adair_ugv_1 --out $W/$O/detail_$T.csv --duration 330 > $W/$O/detail_$T.log 2>&1 < /dev/null & echo \$! > /tmp/detail_$T.pid)"
cd $HK && env UGV_MAX_SPEED_KMH=20 UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $T --rid A-ugv1 --model adair_ugv_1 --target 38.06325574385999 128.17025179536637 --track-s 240 --post-stop-s 35 --world ab_route_v1
