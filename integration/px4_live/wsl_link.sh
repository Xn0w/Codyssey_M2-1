#!/usr/bin/env bash
# integration/px4_live/wsl_link.sh <instance> stop|start — PX4 인스턴스의 Windows 쪽 MAVLink 링크(14590+i → 호스트 14540+i)를 끊거나 잇는다
# (에이전트–PX4 연결 단절 시험. PX4 기본 localhost 링크는 그대로)
I=$1; ACT=$2
B=$HOME/PX4-Autopilot/build/px4_sitl_default/bin/px4-mavlink
H=$(ip route | awk '/^default/ {print $3; exit}')
if [ "$ACT" = stop ]; then
  "$B" --instance "$I" stop -u $((14590 + I))
else
  "$B" --instance "$I" start -x -u $((14590 + I)) -o $((14540 + I)) -t "$H" -m onboard -r 4000000
fi
echo "rc=$? link $ACT instance $I host $H"
