#!/usr/bin/env bash
# 체인24 (38aa911) 뒤: 정지 재검증 고장·취소만 (새 스폰 — 목표 교체 뒤 소방차 갇힘이 UGV 시험을 막지 않게). 코드 = 같은 커밋 (작업트리 그대로)
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
until grep -q "CHAIN24_DONE" logs/ugv/stage4/chain24.out 2>/dev/null; do sleep 20; done
git -C ../ADAIR_wt_comp log --oneline -1
bash logs/ugv/stage4/run_sc_wt.sh c25_stopv logs/ugv/stage4/pair_a_spawn.txt logs/ugv/stage4/pair_a_fleet.json $PY logs/ugv/stage4/stop_verify.py --scenarios fault,abort
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/ugv/tools/px4-stop.sh >/dev/null 2>&1
echo "CHAIN25_DONE $(date)"
