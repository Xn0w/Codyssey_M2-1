#!/usr/bin/env bash
# integration/px4_live/wsl_world.sh — (WSL 안에서) 트윈 지형 타일 구역 월드 하나에 UAV(x500)·UGV 를 함께 띄운다.
#   WORLD=tz_a33 PART=adair_integ STATE=~/.adair-integ bash integration/px4_live/wsl_world.sh <스폰 파일>
#   스폰 파일 한 줄 = "INSTANCE MODEL x,y,z,yaw 자원ID" (ugv/tools/wsl_start_fleet.sh 와 같은 형식, MODEL: x500 / adair_ugv / adair_firetruck)
# Gazebo 는 UGV 시험 스크립트(ugv/tools/px4-stop.sh 의 pkill 무늬 "gz sim --verbose=N -r -s")에 걸리지 않게 인자 순서를 바꿔 띄우고,
# 파티션·상태 폴더를 나눠 다른 시험과 섞이지 않게 한다. 실시간 배율 1 (PX4_SIM_SPEED_FACTOR 1, 월드 real_time_factor 1).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORLD="${WORLD:-tz_a33}"
TILES="$REPO/logs/ugv/stage5/tiles"
export GZ_PARTITION="${PART:-adair_integ}" STATE_DIR="${STATE:-$HOME/.adair-integ}"
BUILD=${PX4_DIR:-$HOME/PX4-Autopilot}/build/px4_sitl_default
mkdir -p "$STATE_DIR"
export GZ_SIM_RESOURCE_PATH="$TILES:${GZ_SIM_RESOURCE_PATH:-}" GZ_SIM_SYSTEM_PLUGIN_PATH="${GZ_SIM_SYSTEM_PLUGIN_PATH:-}"
. "$BUILD/rootfs/gz_env.sh"
export GZ_SIM_RESOURCE_PATH="$REPO/ugv/gazebo/models:$REPO/ugv/gazebo/worlds:$TILES:$GZ_SIM_RESOURCE_PATH"
export GZ_IP=127.0.0.1
up() { gz service -i --service "/world/$WORLD/scene/info" 2>&1 | grep -q "Service providers"; }
if ! up; then
  nohup gz sim -r -s --verbose=2 "$TILES/$WORLD.sdf" > "$STATE_DIR/gz-server.log" 2>&1 &
  echo $! > "$STATE_DIR/gz-integ.pid"
  for _ in $(seq 120); do up && break; sleep 1; done
  up || { echo "월드가 뜨지 않음 ($STATE_DIR/gz-server.log)"; exit 1; }
fi
while read -r INST MODEL POSE RID; do
  [ -z "$INST" ] && continue
  echo "== $RID (instance $INST, $MODEL)"
  WORLD="$WORLD" WORLD_FILE="$TILES/$WORLD.sdf" INSTANCE="$INST" MODEL="$MODEL" POSE="$POSE" \
    "$REPO/ugv/tools/px4-start.sh" | tail -2
done < <(sed 's/\r$//' "$1")
