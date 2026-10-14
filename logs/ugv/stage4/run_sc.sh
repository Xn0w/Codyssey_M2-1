#!/usr/bin/env bash
# bash logs/ugv/stage4/run_sc.sh <tag> <spawn file> <fleet json> <command...>
# 무화재 시험 명시 (환경 서버 UGV_ENV_URL 을 주면 그 자료 상태를 쓴다)
export UGV_ALLOW_NO_FIRE_DATA=${UGV_ALLOW_NO_FIRE_DATA:-1}
cd "$(dirname "$0")/../../.."
TAG=$1; SPAWN=$2; FLEET=$3; shift 3
rm -rf "logs/ugv/stage4/state_$TAG"     # 같은 이름 이전 실행의 상태(임무 기록)가 섞이지 않게
R=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR
P=$(netstat -ano -p TCP | awk '$2 ~ /:8100$/ && $4=="LISTENING" {print $5}' | head -1); [ -n "$P" ] && taskkill //F //T //PID $P >/dev/null 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd $R && bash ugv/tools/px4-stop.sh --params >/dev/null && bash ugv/tools/wsl_start_fleet.sh $SPAWN | grep MAVLink"
UGV_TEST_HOOKS=1 UGV_VEHICLES_JSON=$FLEET UGV_DRIVER=px4 UGV_STATE_DIR="$(pwd)/logs/ugv/stage4/state_$TAG" PYTHONIOENCODING=utf-8 \
  .venv/Scripts/python.exe -m uvicorn ugv.server:app --host 127.0.0.1 --port 8100 > logs/ugv/stage4/server_$TAG.log 2>&1 &
SP=$!
N=$(grep -c . $SPAWN)
until [ "$(curl -s -H 'X-ADAIR-Monitor: 1' http://127.0.0.1:8100/ugv 2>/dev/null | grep -o '"state":"READY"' | wc -l)" -ge "$N" ]; do sleep 2; done
PYTHONIOENCODING=utf-8 "$@" > logs/ugv/stage4/$TAG.out 2>&1
taskkill //F //T //PID "$(cat /proc/$SP/winpid)" >/dev/null 2>&1; sleep 2
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash $R/logs/ugv/stage4/wsl_copy_logs.sh $R/logs/ugv/stage4 $TAG
grep "기록:" logs/ugv/stage4/$TAG.out
