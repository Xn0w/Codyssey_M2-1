#!/usr/bin/env bash
# 2026-10-13 S4 명령 기준 제동 — 서버와 같은 정차 유지 정책(UGV_DRIVE_PARK=server: 미션 끝 뒤 1 s 정차 또는 4 s 상한에 시동 끔)으로.
# chain_s4 의 정책 없는 회차(a·b·c)는 PX4 단독 거동 기록으로 남기고, 시스템 정지거리는 이 묶음(회차 pa·pb·pc)으로 잰다.
# 차종별: 비상·취소 정지 × 2속도 + 임무 도착(30, 최고속도) 각 3회. 끝나면 chain_s4b(회전·무게중심)를 같은 정책으로.
cd "$(dirname "$0")/../../.."
export UGV_DRIVE_PARK=server
F=adair_firetruck
L=""
for sc in estop50 estop30 cancel50 cancel30 stop30 straight50; do for r in pa pb pc; do L="$L fire_v2:adair_flat:$sc:$r:$F"; done; done
for sc in estop60 estop30 cancel60 cancel30 stop30 straight; do for r in pa pb pc; do L="$L susp_a:adair_flat:$sc:$r"; done; done
bash logs/ugv/stage6/run_drive_v2c.sh $L > logs/ugv/stage6/drive_s4p.out 2>&1
echo "CHAIN_S4P_DONE $(date)"
