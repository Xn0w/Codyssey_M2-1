#!/usr/bin/env bash
# (통합 시험 뒤) 4번 대조: 실제 지형 같은 경로 원기둥 바퀴 / 최종 코드 정지 재확인 (고장·취소 — acd404f 정지 경로 가속 수정)
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
git -C ../ADAIR_wt_comp checkout -q --detach feat/orchestrator-final
TGT=RP:682501271:39.7
UGV_MAX_SPEED_KMH=30 WORLD=tz_a33 bash logs/ugv/stage4/run_sc_tz.sh c17_real_ugv logs/ugv/stage4/tz_a33_spawn_ugv.txt logs/ugv/stage4/single_a_fleet.json $PY -m ugv.tools.road_test --tag c17_real_ugv --rid A-ugv1 --model adair_ugv_1 --target-node $TGT --return-home --track-s 600 --world tz_a33
$PY logs/ugv/stage4/grip_compare.py --glob 'logs/ugv/c1[67]_*ugv*.json' > logs/ugv/stage4/grip_compare_c17.txt 2>&1
bash logs/ugv/stage4/run_sc_wt.sh c17_stopv logs/ugv/stage4/pair_a_spawn.txt logs/ugv/stage4/pair_a_fleet.json $PY logs/ugv/stage4/stop_verify.py --scenarios fault,abort
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/ugv/tools/px4-stop.sh >/dev/null 2>&1
echo CHAIN17_DONE
