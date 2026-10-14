#!/usr/bin/env bash
# 2026-10-13 간헐 실패 고정 장면 최소 비교 (Codex 답변 1548 (가)) — sim, Gazebo 없음.
#   고장·정지 뒤 A 를 원래 실패 회차(flaky_diag_v3 run00) 최종 자세 (3945.123, 5561.727, 226.42) 에 배치·고정 → B 만 비교.
#   배속 축 (2차): 같은 고정 장면 3배속 origin ↔ footprint 각 5회 — 30배 결과(flaky_frz F1·F2)와 비교. STALE 이 배속 산물인지 확인. 유효성 = fixture (A 고정 유지·도로 3개 점유) 만 —
#   B 충돌·교통 판정·도착·TIMEOUT 은 결과 지표 (flaky_post 고정 장면판). 기준 결과 전 고정. 25회 행렬 반복 아님.
cd "$(dirname "$0")/../../../.."
S6=../ADAIR/logs/ugv/stage6; PY=../ADAIR/.venv/Scripts/python.exe; O=$S6/flaky_frz
cd ADAIR_wt_integ && mkdir -p $O
echo "{\"head\": \"$(git rev-parse HEAD)\", \"dirty\": \"$(git status --porcelain --untracked-files=no | tr '\n' ' ')\", \"diag_sha1\": \"$(sha1sum $S6/flaky_diag.py | cut -c1-40)\", \"post_sha1\": \"$(sha1sum $S6/flaky_post.py | cut -c1-40)\", \"frozen_a\": [3945.123, 5561.727, 226.42]}" > $O/manifest_x3.json
run() { mkdir -p $O/$1; UGV_BLOCK_AVOID=$2 PYTHONIOENCODING=utf-8 timeout 3000 $PY $S6/flaky_diag.py 5 $O/$1 --frozen-a 3945.123 5561.727 226.42 $3 > $O/$1/diag.out 2>&1; echo "$1 rc=$? $(grep DIAG_SUMMARY $O/$1/diag.out)"; PYTHONIOENCODING=utf-8 $PY $S6/flaky_post.py $O/$1 > $O/$1/post.out 2>&1; echo "  $(grep POST_SUMMARY $O/$1/post.out | cut -c1-400)"; }
{
run F3_frozen_origin_x3 origin "--scale 3"
run F4_frozen_footprint_x3 footprint "--scale 3"
} > $O/summary_x3.txt 2>&1
echo "CHAIN_SIMFRZ_DONE $(date) $(tr '\n' ' ' < $O/summary.txt | cut -c1-900)"
