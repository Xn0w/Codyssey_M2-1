#!/usr/bin/env bash
# 2026-10-13 간헐 실패 개입 비교 2차 (1차 I1~I4 는 고장 차가 도로 661 하나에만 서 원래 실패 장면(교차로 도로 3개 점유) 미재현 → 주입 범위를 원래 실패 s 46.0 에 맞춰 [44,48]). (sim, Gazebo 없음 — chain_slope 와 chain_s4i 사이). 진단 v3(20회) 결과: 교차로 정지(도로 3개 점유) 5/5 실패, 도로 중간 15/15 도착.
# 조건 × 5회: I1 교차로 s[30,50]·origin·30배 / I2 도로 중간 s[55,70]·origin·30배 / I3 교차로·footprint·30배 / I4 교차로·origin·3배 / I5 교차로·footprint·3배
# 도착까지만 보는 관찰 — 전체 폐루프 합격 수 아님. DONE = 묶음 끝.
cd "$(dirname "$0")/../../../.."
until grep -q CHAIN_XSLOPE_DONE ADAIR/logs/ugv/stage6/chain_xslope.out 2>/dev/null; do sleep 30; done
S6=../ADAIR/logs/ugv/stage6; PY=../ADAIR/.venv/Scripts/python.exe; O=$S6/flaky_int2
cd ADAIR_wt_integ && mkdir -p $O
echo "{\"head\": \"$(git rev-parse HEAD)\", \"dirty\": \"$(git status --porcelain --untracked-files=no | tr '\n' ' ')\", \"diag_sha1\": \"$(sha1sum $S6/flaky_diag.py | cut -c1-40)\"}" > $O/manifest.json
run() { mkdir -p $O/$1; UGV_BLOCK_AVOID=$2 PYTHONIOENCODING=utf-8 timeout 3000 $PY $S6/flaky_diag.py 5 $O/$1 --fault-s $3 $4 $5 > $O/$1/diag.out 2>&1; echo "$1 rc=$? $(grep DIAG_SUMMARY $O/$1/diag.out)"; PYTHONIOENCODING=utf-8 $PY $S6/flaky_post.py $O/$1 > $O/$1/post.out 2>&1; }
{
run J1_junction46_origin_x30 origin 44 48 ""
run J2_midroad_origin_x30 origin 55 70 ""
run J3_junction46_footprint_x30 footprint 44 48 ""
run J4_junction46_origin_x3 origin 44 48 "--scale 3"
run J5_junction46_footprint_x3 footprint 44 48 "--scale 3"
} > $O/summary.txt 2>&1
echo "CHAIN_SIMINT2_DONE $(date) $(tr '\n' ' ' < $O/summary.txt)"
