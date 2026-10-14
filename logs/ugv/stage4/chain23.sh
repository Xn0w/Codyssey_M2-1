#!/usr/bin/env bash
# 최종 코드 (f3369fe): 목표 교체·고장·취소 재확인 → 지속 운용 40 분 (20 분째 서버 재시작)
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
git -C ../ADAIR_wt_comp checkout -q --detach feat/orchestrator-final
bash logs/ugv/stage4/run_sc_wt.sh c23_stopv logs/ugv/stage4/pair_a_spawn.txt logs/ugv/stage4/pair_a_fleet.json $PY logs/ugv/stage4/stop_verify.py --scenarios retarget,fault,abort
bash logs/ugv/stage4/run_sc_wt.sh c23_soak ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY logs/ugv/stage4/soak.py --minutes 40 --restart-at 20 --restart-cmd "\"C:/Program Files/Git/usr/bin/bash.exe\" logs/ugv/stage4/restart_server_wt.sh c23_soak ugv/fleet_ab.json"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/ugv/tools/px4-stop.sh >/dev/null 2>&1
echo CHAIN23_DONE
