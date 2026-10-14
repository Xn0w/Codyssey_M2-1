#!/usr/bin/env bash
# chain_s4 가 지금 회차를 끝내고 다음 회차(사전 정지 단계)를 시작하는 순간 멈추고, chain_s4p → chain_s4b 로 넘긴다.
cd "$(dirname "$0")"
n0=$(grep -c "^== " drive_s4.out)
until [ $(grep -c "^== " drive_s4.out) -gt $n0 ] || grep -q RUN_DRIVE_DONE drive_s4.out; do sleep 1; done
NEXT=$(grep "^== " drive_s4.out | tail -1 | awk '{print $2}')
for p in $(ps -ef | grep -E "[c]hain_s4.sh|[r]un_drive_v2.sh" | awk '{print $2}'); do kill $p 2>/dev/null; done
echo "chain_s4 중단 $(date +%T) — 시작 직전 회차 $NEXT (사전 정지 단계, 시험 안 함)" | tee -a drive_s4.out
echo "CHAIN_S4_STOPPED_FOR_PARK $(date)" >> chain_s4.out
sleep 20
(nohup bash chain_s4p.sh > chain_s4p.out 2>&1 &)
(nohup bash chain_s4b.sh > chain_s4b.out 2>&1 &)
echo "switched $NEXT"
