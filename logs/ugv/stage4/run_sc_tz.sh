#!/usr/bin/env bash
# 트윈 지형 타일 구역 월드 시험: run_sc_wt.sh 와 같고 월드 = logs/ugv/stage5/tiles/<WORLD>.sdf, 도로 = 그 구역 부분집합
# WORLD=tz_a33 bash logs/ugv/stage4/run_sc_tz.sh <tag> <spawn> <fleet> <command...>   (추가 서버 환경변수는 그대로 전달)
# 무화재 시험 명시 (환경 서버 UGV_ENV_URL 을 주면 그 자료 상태를 쓴다)
export UGV_ALLOW_NO_FIRE_DATA=${UGV_ALLOW_NO_FIRE_DATA:-1}
cd "$(dirname "$0")/../../.."
TAG=$1; SPAWN=$2; FLEET=$3; shift 3
rm -rf "logs/ugv/stage4/state_$TAG"     # 같은 이름 이전 실행의 상태(임무 기록)가 섞이지 않게
M=$(pwd)
R=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR
W=${WORLD:?WORLD 필요}
P=$(netstat -ano -p TCP | awk '$2 ~ /:8100$/ && $4=="LISTENING" {print $5}' | head -1); [ -n "$P" ] && taskkill //F //T //PID $P >/dev/null 2>&1
T0=$(date +%s)
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd $R && bash ugv/tools/px4-stop.sh --params >/dev/null && GZ_MODEL_OVERRIDE=${GZ_MODEL_OVERRIDE:-} WORLD=$W WORLD_FILE=$R/logs/ugv/stage5/tiles/$W.sdf GZ_SIM_RESOURCE_PATH=$R/logs/ugv/stage5/tiles bash ugv/tools/wsl_start_fleet.sh $SPAWN | grep MAVLink"
echo "$TAG gz+px4 기동 $(( $(date +%s) - T0 )) s" >> logs/ugv/stage4/tz_startup.txt
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "ps -o rss=,vsz=,cmd= -C gz | head -3; free -m | head -2" >> logs/ugv/stage4/tz_startup.txt 2>&1
cd ../ADAIR_wt_comp
UGV_TEST_HOOKS=1 UGV_VEHICLES_JSON=$M/$FLEET UGV_DRIVER=px4 UGV_STATE_DIR="$M/logs/ugv/stage4/state_$TAG" UGV_ROAD_SUBSET="$M/logs/ugv/stage5/tiles/road_subset_$W.json" \
  PYTHONIOENCODING=utf-8 ../ADAIR/.venv/Scripts/python.exe -m uvicorn ugv.server:app --host 127.0.0.1 --port 8100 > $M/logs/ugv/stage4/server_$TAG.log 2>&1 &
SP=$!
cd "$M"
N=$(grep -c . $SPAWN)
until [ "$(curl -s -H 'X-ADAIR-Monitor: 1' http://127.0.0.1:8100/ugv 2>/dev/null | grep -o '"state":"READY"' | wc -l)" -ge "$N" ]; do sleep 2; done
UGV_GZ_WORLD=$W PYTHONIOENCODING=utf-8 "$@" > logs/ugv/stage4/$TAG.out 2>&1
taskkill //F //T //PID "$(cat /proc/$SP/winpid)" >/dev/null 2>&1; sleep 2
P=$(netstat -ano -p TCP | awk '$2 ~ /:8100$/ && $4=="LISTENING" {print $5}' | head -1); [ -n "$P" ] && taskkill //F //T //PID $P >/dev/null 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash $R/logs/ugv/stage4/wsl_copy_logs.sh $R/logs/ugv/stage4 $TAG
grep "기록:" logs/ugv/stage4/$TAG.out
