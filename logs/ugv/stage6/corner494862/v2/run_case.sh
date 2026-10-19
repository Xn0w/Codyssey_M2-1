#!/usr/bin/env bash
# run_corner.sh 의 매개변수판 (2026-10-19 검증보완계획 §5): 같은 월드(ab_route_v1, tiles_v2c1)·차량 모델·PX4 기동·UGV 서버 설정(UGV_LAT_ACCEL=1.0, 도로 부분집합).
# 출발 자세·차량 설정·목표·서버 소스 트리만 바꾼다. run_corner.sh 는 그대로 둔다.
# 사용: run_case.sh <TAG> <서버 트리 절대경로(Windows git-bash 경로)> <사례 폴더(spawn.txt·fleet.json·case.json 또는 원 경로면 corner)> [추가 서버 환경 KEY=VAL ...]
#   사례 폴더 = corner → 원 경로 (corner494862 spawn_c.txt, fleet_c.json, RP:682500789:49.1)
#   출력: logs/ugv/stage6/corner494862/v2/runs/<TAG>
set -u
cd "$(dirname "$0")/../../../../.."
M=$(pwd); T=$1; SRV=$2; CASE=$3; shift 3
D=logs/ugv/stage6/corner494862; O=$D/v2/runs/$T
[ -e "$O" ] && { echo "$T 이미 있음"; exit 9; }
mkdir -p $O
W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR
PY=$M/.venv/Scripts/python.exe
SUB=$M/logs/ugv/stage5/tiles_v2c1/road_subset_ab_route_v1.json
if [ "$CASE" = corner ]; then
  SPAWN=$D/spawn_c.txt; FLEET=$M/$D/fleet_c.json; TGT=RP:682500789:49.1
else
  CD=$D/v2/cases/$CASE; SPAWN=$CD/spawn.txt; FLEET=$M/$CD/fleet.json
  TGT=$($PY -c "import json;print(json.load(open('$CD/case.json',encoding='utf-8'))['target_node'])")
fi
wslx() { MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "$1"; }
P=$(netstat -ano -p TCP | awk '$2 ~ /:8100$/ && $4=="LISTENING" {print $5}' | head -1); [ -n "$P" ] && { echo "8100 사용 중 (PID $P) — 이 시험이 띄운 것이 아니므로 중단"; exit 8; }
wslx "STATE=\$HOME/.adair-integ bash $W/integration/px4_live/wsl_stop.sh --params" > $O/stop_pre.txt 2>&1
echo "{\"tag\":\"$T\",\"server_tree\":\"$SRV\",\"server_head\":\"$(git -C $SRV rev-parse --short HEAD)$(git -C $SRV status --porcelain -- ugv | grep -q . && echo -dirty)\",\"ugv_diff_sha256\":\"$(git -C $SRV diff HEAD -- ugv | sha256sum | cut -c1-16)\",\"case\":\"$CASE\",\"target\":\"$TGT\",\"spawn\":\"$(cat $SPAWN | tr -d '\r\n')\",\"extra_env\":\"$*\",\"time\":\"$(date -Is)\"}" > $O/manifest.json
wslx "cd $W && WORLD=ab_route_v1 PART=adair_integ STATE=\$HOME/.adair-integ bash logs/integ/wsl_world_b.sh $W/$SPAWN" > $O/wsl_world.log 2>&1
wslx "GZ_PARTITION=adair_integ GZ_IP=127.0.0.1 gz model -m adair_ugv_1 -j 2>&1 | grep -iE 'name|type' | head -60" > $O/gz_joints.txt 2>&1
echo "susp_joints=$(grep -c 'susp_' $O/gz_joints.txt)" | tee $O/model_check.txt
( cd $SRV && env "$@" UGV_DRIVER=px4 UGV_VEHICLES_JSON=$FLEET UGV_ROAD_SUBSET=$SUB UGV_TIME_SCALE=1 UGV_LAT_ACCEL=1.0 \
    UGV_ALLOW_NO_FIRE_DATA=1 UGV_STATE_DIR=$M/$O/state PYTHONIOENCODING=utf-8 $PY -m uvicorn ugv.server:app --host 127.0.0.1 --port 8100 > $M/$O/server.log 2>&1 ) &
OK=0; T1=$(date +%s)
while [ $(( $(date +%s) - T1 )) -lt 180 ]; do
  curl -s -H 'X-ADAIR-Monitor: 1' http://127.0.0.1:8100/ugv 2>/dev/null | grep -q '"state":"READY"' && { OK=1; break; }; sleep 2
done
echo "ready=$OK" | tee $O/ready.txt
if [ $OK = 1 ]; then
  ( cd $SRV && env "$@" UGV_GZ_PARTITION=adair_integ UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$M/logs/ugv/stage5/tiles_v2c1 \
      PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 $PY -m ugv.tools.road_test --rid A-ugv1 --model adair_ugv_1 --world ab_route_v1 \
      --target-node $TGT --track-s 240 --tag corner_$T ) > $O/road_test.out 2>&1
  cp $SRV/logs/ugv/road_corner_${T}* $O/ 2>/dev/null; cp $SRV/logs/ugv/*corner_${T}* $O/ 2>/dev/null
  curl -s http://127.0.0.1:8100/ugv/A-ugv1/route > $O/route_final.json
  curl -s -H 'X-ADAIR-Monitor: 1' http://127.0.0.1:8100/ugv > $O/ugv_final.json
fi
P=$(netstat -ano -p TCP | awk '$2 ~ /:8100$/ && $4=="LISTENING" {print $5}' | head -1); [ -n "$P" ] && taskkill //F //T //PID $P >/dev/null 2>&1
wslx "STATE=\$HOME/.adair-integ bash $W/integration/px4_live/wsl_stop.sh" > $O/stop_post.txt 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash $W/integration/px4_live/wsl_copy_ulog.sh .adair-integ $W/$O/ulog > /dev/null 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- python3 $W/$D/ulog_speed.py $W/$O/ulog/px4-1.ulg $W/$O/ulog_speed.csv > $O/ulog_speed.txt 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- python3 -c "from pyulog import ULog; u=ULog('$W/$O/ulog/px4-1.ulg',[]); p=u.initial_parameters; print({k:p.get(k) for k in ('NAV_ACC_RAD','RA_ACC_RAD_MAX','RO_SPEED_LIM','GND_SPEED_MAX') if k in p})" > $O/px4_params.txt 2>&1
LEFT=$(MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc 'pgrep -af "[g]z sim|[b]in/px4|[g]z_bridge"'); echo "leftover=[$LEFT]" > $O/leftover.txt
echo "CASE_DONE $T ready=$OK"
