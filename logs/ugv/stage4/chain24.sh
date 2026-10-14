#!/usr/bin/env bash
# 최종 후보 커밋 하나로: 교차로 정차 갇힘 Gazebo 재현(원위치·±0.2 m) → 정지 재검증(목표 교체·고장·취소) → UAV+UGV+총괄 20 분 통합
# → 지속 운용 40 분(20 분째 재시작). 중간에 코드 변경 없음 (커밋 해시 인자).
#   bash logs/ugv/stage4/chain24.sh <commit>
cd "$(dirname "$0")/../../.."
RC=$1
PY=.venv/Scripts/python.exe
[ -z "$RC" ] && { echo "커밋 해시 필요"; exit 1; }
# (앞선 참고용 통합 실행은 시작 전에 끝났음을 확인하고 띄운다)
echo "== 시작 $(date) RC=$RC"
git -C ../ADAIR_wt_comp checkout -q --detach "$RC" && git -C ../ADAIR_wt_comp log --oneline -1
for i in 0 1 2; do
  bash logs/ugv/stage4/run_sc_wt.sh c24_junc$i logs/ugv/stage4/junc_spawn_$i.txt logs/ugv/stage4/single_fire1_fleet.json $PY logs/ugv/stage4/junction_verify.py --label $i
done
bash logs/ugv/stage4/run_sc_wt.sh c24_stopv logs/ugv/stage4/pair_a_spawn.txt logs/ugv/stage4/pair_a_fleet.json $PY logs/ugv/stage4/stop_verify.py --scenarios retarget,fault,abort
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/ugv/tools/px4-stop.sh >/dev/null 2>&1
# 통합은 메인 작업트리에서 (logs/ 자료) — 메인 트리를 같은 커밋으로
git merge -q --ff-only "$RC" && git log --oneline -1
[ "$(git rev-parse HEAD)" = "$(git rev-parse "$RC")" ] || { echo "메인 트리 커밋 불일치 — 통합 생략"; exit 1; }
PYTHONIOENCODING=utf-8 $PY integration/px4_live/run_integ.py run --minutes 35 > logs/integ/final4.out 2>&1
echo "INTEG_DONE $(date)"
# 마지막: 지속 운용 40 분 (시간이 모자라면 중간 기록 .partial.json 까지가 근거)
bash logs/ugv/stage4/run_sc_wt.sh c24_soak ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY logs/ugv/stage4/soak.py --minutes 40 --restart-at 20 --restart-cmd "\"C:/Program Files/Git/usr/bin/bash.exe\" logs/ugv/stage4/restart_server_wt.sh c24_soak ugv/fleet_ab.json"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/ugv/tools/px4-stop.sh >/dev/null 2>&1
echo "CHAIN24_DONE $(date)"
