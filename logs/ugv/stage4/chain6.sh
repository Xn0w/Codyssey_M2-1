#!/usr/bin/env bash
# 7단계 지속 운용 (평탄 A 월드 4대, 작업트리 코드): 120 분, 60 분째 서버 재시작
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
bash logs/ugv/stage4/run_sc_wt.sh c6_soak ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY logs/ugv/stage4/soak.py --minutes 120 --restart-at 60 --restart-cmd "\"C:/Program Files/Git/usr/bin/bash.exe\" logs/ugv/stage4/restart_server_wt.sh c6_soak ugv/fleet_ab.json"
echo CHAIN6_DONE
