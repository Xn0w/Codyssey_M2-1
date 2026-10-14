#!/usr/bin/env bash
# 38aa911 (코드 동결): 20 분 통합 재실행 (final4 는 총괄 배치 스레드 멈춤으로 무효) → 정지 재검증 고장·취소 (새 스폰) → 지속 운용 (남는 시간)
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
git log --oneline -1; git -C ../ADAIR_wt_comp log --oneline -1
( until [ -f logs/integ/final5.out ]; do sleep 3; done; PYTHONIOENCODING=utf-8 $PY integration/px4_live/start_item_watch.py logs/integ/final5_start_items.jsonl --minutes 40 > logs/integ/final5_watch.out 2>&1 ) &
PYTHONIOENCODING=utf-8 $PY integration/px4_live/run_integ.py run --minutes 35 > logs/integ/final5.out 2>&1
echo "INTEG_DONE $(date)"
bash logs/ugv/stage4/run_sc_wt.sh c26_stopv logs/ugv/stage4/pair_a_spawn.txt logs/ugv/stage4/pair_a_fleet.json $PY logs/ugv/stage4/stop_verify.py --scenarios fault,abort
echo "STOPV_DONE $(date)"
bash logs/ugv/stage4/run_sc_wt.sh c26_soak ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY logs/ugv/stage4/soak.py --minutes 40 --restart-at 20 --restart-cmd "\"C:/Program Files/Git/usr/bin/bash.exe\" logs/ugv/stage4/restart_server_wt.sh c26_soak ugv/fleet_ab.json"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/ugv/tools/px4-stop.sh >/dev/null 2>&1
echo "CHAIN26_DONE $(date)"
