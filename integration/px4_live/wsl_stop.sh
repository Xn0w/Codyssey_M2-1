#!/usr/bin/env bash
# integration/px4_live/wsl_stop.sh — wsl_world.sh 로 띄운 것만 끈다 (상태 폴더의 pid 파일 기준. 다른 시험의 Gazebo·PX4 는 건드리지 않는다)
STATE_DIR="${STATE:-$HOME/.adair-integ}"
for f in "$STATE_DIR"/px4-*.pid "$STATE_DIR"/gz-integ.pid; do
  [ -f "$f" ] || continue
  kill "$(cat "$f")" 2>/dev/null || true
  rm -f "$f"
done
[ "${1:-}" = "--params" ] && rm -f "$STATE_DIR"/px4-*/parameters*.bson "$STATE_DIR"/px4-*/dataman 2>/dev/null
echo "[integ] 종료 ($STATE_DIR)"
