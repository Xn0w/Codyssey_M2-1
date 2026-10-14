#!/usr/bin/env bash
# 다른 PC 의 WSL (Ubuntu-24.04) 에서 UGV 스크립트의 /home/geumsoni/PX4-Autopilot 경로를 그대로 쓰게 하는 연결. 사용: bash setup_paths_wsl.sh [PX4 폴더]
# /home/geumsoni/PX4-Autopilot → 이 PC 의 PX4-Autopilot (기본 $HOME/PX4-Autopilot). sudo 필요 (/home 아래 폴더 생성).
# /mnt/c/Users/수다쟁이고양이들 은 Windows 쪽 setup_paths_windows.ps1 의 junction 으로 해결됨 — 여기서 확인만.
set -e
PX4="${1:-$HOME/PX4-Autopilot}"
[ -d "$PX4" ] || { echo "PX4 폴더 없음: $PX4 (PX4-Autopilot SITL 빌드 먼저)"; exit 1; }
if [ "$(readlink -f /home/geumsoni/PX4-Autopilot 2>/dev/null)" = "$(readlink -f "$PX4")" ]; then echo "이미 연결/원래 PC: /home/geumsoni/PX4-Autopilot"
elif [ -e /home/geumsoni/PX4-Autopilot ]; then echo "/home/geumsoni/PX4-Autopilot 가 이미 있고 다른 곳 — 손대지 않음"; exit 1
else sudo mkdir -p /home/geumsoni && sudo ln -s "$PX4" /home/geumsoni/PX4-Autopilot && echo "연결 만듦: /home/geumsoni/PX4-Autopilot -> $PX4"; fi
for r in ADAIR ADAIR_wt_hook ADAIR_wt_vehicle; do d="/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/$r"; [ -d "$d" ] && echo "확인: $d" || echo "없음 (Windows junction·저장소 확인): $d"; done
