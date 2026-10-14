#!/usr/bin/env bash
# A 단계 시험 명령 v2 (testcmd.sh 의 기록기 기동 결함 수정 — 2026-10-14 tb2 출력 0): 고율 기록기를 띄운 뒤 **같은 WSL 세션 안에서** 3 s 기다려
# 프로세스 생존 + CSV 2 줄 이상 확인 (run_sc_v9 gz_rec 기동과 같은 방식). 실패면 road_test 를 실행하지 않고 종료 코드 11 (래퍼 test_rc ≠ 0 → 무효).
T=$1; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR; O=logs/ugv/stage6/terrain_ab/envB_c1
M=$(pwd); ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe; HK=../ADAIR_wt_hook; SUB=$ST/tiles_v2/road_subset_ab_route_v1.json
R=$(MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "export GZ_PARTITION=adair_ugv GZ_IP=127.0.0.1; (setsid nohup python3 $W/logs/ugv/stage6/terrain_ab/seamR/gz_detail_seam.py --world ab_route_v1 --model adair_ugv_1 --out $W/$O/detail_$T.csv --duration 330 > $W/$O/detail_$T.log 2>&1 < /dev/null & echo \$! > /tmp/detail_$T.pid); sleep 3; P=\$(cat /tmp/detail_$T.pid); if ps -p \$P > /dev/null && [ \$(wc -l < $W/$O/detail_$T.csv 2>/dev/null || echo 0) -ge 2 ]; then echo DETAIL_STARTED; else echo DETAIL_NOT_RUNNING; fi" | tr -d '\r')
echo "$R" > $O/detail_start_$T.txt
[ "$R" = DETAIL_STARTED ] || { echo "고율 기록기 기동 실패 ($R) — road_test 안 함"; exit 11; }
cd $HK && env UGV_MAX_SPEED_KMH=20 UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $T --rid A-ugv1 --model adair_ugv_1 --target 38.06325574385999 128.17025179536637 --track-s 240 --post-stop-s 35 --world ab_route_v1
