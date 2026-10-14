#!/usr/bin/env bash
# WSL 안에서: gz·PX4 텍스트 로그를 시험 이름으로 복사.  bash wsl_copy_logs.sh <대상 폴더(WSL 경로)> <tag>
D=$1; T=$2
cp ~/.adair-ugv/gz-server.log "$D/gz-server_$T.log" 2>/dev/null
for i in 1 2 3 4; do
  [ -f ~/.adair-ugv/px4-$i.log ] && cp ~/.adair-ugv/px4-$i.log "$D/px4-${i}_$T.log"
done
ls ~/.adair-ugv/px4-1/log/$(date -u +%F)/ 2>/dev/null | tail -1 > "$D/ulog_last_$T.txt"
