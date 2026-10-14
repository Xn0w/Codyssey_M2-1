#!/usr/bin/env bash
# 최종 코드 지속 운용 (평탄 A 월드 4대): 60 분, 30 분째 서버 재시작 — 수정 전후가 섞인 c6 를 대신하는 새 시험
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
git -C ../ADAIR_wt_comp checkout -q --detach feat/orchestrator-final
bash logs/ugv/stage4/run_sc_wt.sh c18_soak ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY logs/ugv/stage4/soak.py --minutes 60 --restart-at 30 --restart-cmd "\"C:/Program Files/Git/usr/bin/bash.exe\" logs/ugv/stage4/restart_server_wt.sh c18_soak ugv/fleet_ab.json"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/ugv/tools/px4-stop.sh >/dev/null 2>&1
echo CHAIN18_DONE
