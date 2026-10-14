#!/usr/bin/env bash
# 4단계 Gazebo: 총괄 폐루프(loop·fault·blocked) → 화재(실제 환경 스냅샷·같은 입력 재현) → 총괄 통신 단절 실제 벽시계
# 서버 = 작업트리 코드 (run_sc_wt.sh). 환경 서버 :8301 (이번 작업이 띄움, tick 6 상태) 가 떠 있어야 한다
cd "$(dirname "$0")/../../.."
PY=.venv/Scripts/python.exe
RW=logs/ugv/stage4/run_sc_wt.sh
S=logs/ugv/stage4/single_a_spawn.txt; F=logs/ugv/stage4/single_a_fleet.json
bash $RW c4_orch_loop ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY logs/ugv/stage4/orch_loop.py --scenario loop --tag gz_loop --track-s 1500
bash $RW c4_orch_fault ugv/fleet_ab_spawn.txt ugv/fleet_ab.json $PY logs/ugv/stage4/orch_loop.py --scenario fault --tag gz_fault --track-s 900
bash $RW c4_orch_blocked logs/ugv/pair_static_ahead_spawn.txt logs/ugv/pair_static_ahead_fleet.json $PY logs/ugv/stage4/orch_loop.py --scenario blocked --tag gz_blocked --track-s 300
# 화재 1: 실제 환경 서버 스냅샷 (트윈 설정, 6 단계 = 12600 s, 저장본 logs/ugv/stage4/env_snap/snap_t6.json)
curl -s http://127.0.0.1:8301/snapshot > logs/ugv/stage4/env_snap/snap_used_c4_fire_env.json
UGV_ENV_URL=http://127.0.0.1:8301 bash $RW c4_fire_env $S $F $PY -m ugv.tools.road_test --tag c4_fire_env --target 38.0277 128.1303 --track-s 900 --world kangwon_flat
# 화재 2: 같은 화재 칸을 시험 입력 서버로 재현 (재현 입력 = 저장한 스냅샷)
FIRE_FIXTURE_LOG=logs/ugv/stage4/env_snap/fixture PYTHONIOENCODING=utf-8 $PY -m uvicorn ugv.tools.fire_fixture_server:app --host 127.0.0.1 --port 8310 > logs/ugv/stage4/env_snap/fixture_server.log 2>&1 &
FX=$!
until curl -s http://127.0.0.1:8310/health > /dev/null; do sleep 1; done
$PY -c "
import json, httpx
d = json.load(open('logs/ugv/stage4/env_snap/snap_used_c4_fire_env.json', encoding='utf-8'))
print(httpx.post('http://127.0.0.1:8310/set', json={'label': 'ENV_SNAPSHOT_REPLAY run=%s v=%s' % (d['run_id'], d['state_version']), 'cells': d['fire_cells']}).json())
"
UGV_ENV_URL=http://127.0.0.1:8310 bash $RW c4_fire_replay $S $F $PY -m ugv.tools.road_test --tag c4_fire_replay --target 38.0277 128.1303 --track-s 900 --world kangwon_flat
taskkill //F //T //PID "$(cat /proc/$FX/winpid)" >/dev/null 2>&1
# 총괄 통신 단절 실제 벽시계 (10 분 정지 → 30 분 뒤 복귀). 약 55 분
bash $RW c4_comm_loss $S $F $PY logs/ugv/stage4/comm_loss_wall.py --rid A-ugv1 --target 37.9650816 128.3175278 --track-s 3900
echo CHAIN4_DONE
