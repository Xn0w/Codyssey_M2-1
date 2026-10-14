#!/usr/bin/env bash
# 2026-10-13 S4 개선 후보 검증: 정지 임무 끝 즉시 시동 끔(UGV_DRIVE_PARK=immediate). 서버 정책(4 s 상한) 회차 pa·pb·pc 와 비교 — 회차 ia·ib·ic.
# 한 항목(정차 유지 시점)만 다르다. chain_simint(sim 개입 비교) 뒤에.
cd "$(dirname "$0")/../../.."
until grep -q CHAIN_SIMINT_DONE logs/ugv/stage6/chain_simint.out 2>/dev/null; do sleep 30; done
export UGV_DRIVE_PARK=immediate
F=adair_firetruck; L=""
for sc in estop50 estop30 cancel50; do for r in ia ib ic; do L="$L fire_v2:adair_flat:$sc:$r:$F"; done; done
for sc in estop60 estop30 cancel60; do for r in ia ib ic; do L="$L susp_a:adair_flat:$sc:$r"; done; done
bash logs/ugv/stage6/run_drive_v2c.sh $L > logs/ugv/stage6/drive_s4i.out 2>&1
echo "CHAIN_S4I_DONE $(date)"
