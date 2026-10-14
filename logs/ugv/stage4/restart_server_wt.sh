#!/usr/bin/env bash
# 지속 운용 시험 중 UGV 서버(작업트리 코드) 재시작 — 같은 상태 폴더로 (재시작 뒤 상태 정리·미확인 차량 처리 확인)
# bash logs/ugv/stage4/restart_server_wt.sh <tag> <fleet json>
# 무화재 시험 명시 (환경 서버 UGV_ENV_URL 을 주면 그 자료 상태를 쓴다)
export UGV_ALLOW_NO_FIRE_DATA=${UGV_ALLOW_NO_FIRE_DATA:-1}
cd "$(dirname "$0")/../../.."
TAG=$1; FLEET=$2; M=$(pwd)
P=$(netstat -ano -p TCP | awk '$2 ~ /:8100$/ && $4=="LISTENING" {print $5}' | head -1); [ -n "$P" ] && taskkill //F //T //PID $P >/dev/null 2>&1
sleep 3
cd ../ADAIR_wt_comp
UGV_TEST_HOOKS=1 UGV_VEHICLES_JSON=$M/$FLEET UGV_DRIVER=px4 UGV_STATE_DIR="$M/logs/ugv/stage4/state_$TAG" PYTHONIOENCODING=utf-8 \
  nohup ../ADAIR/.venv/Scripts/python.exe -m uvicorn ugv.server:app --host 127.0.0.1 --port 8100 >> $M/logs/ugv/stage4/server_${TAG}_restart.log 2>&1 &
cd "$M"
until curl -s -H 'X-ADAIR-Monitor: 1' http://127.0.0.1:8100/ugv > /dev/null 2>&1; do sleep 2; done
echo restarted
