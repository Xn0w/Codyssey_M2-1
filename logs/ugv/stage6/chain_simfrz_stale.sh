#!/usr/bin/env bash
# 2026-10-13 간헐 실패 고정 장면 최소 비교 (Codex 답변 1548 (가)) — sim, Gazebo 없음.
#   고장·정지 뒤 A 를 원래 실패 회차(flaky_diag_v3 run00) 최종 자세 (3945.123, 5561.727, 226.42) 에 배치·고정 → B 만 비교.
#   frz2 (Codex 1557): 배치 뒤 A 진행 색인(_near_i)을 고정 자세 기준으로 재설정 — 1차(flaky_frz F1·F2)는 배치 전 실제 정지 s 가 4.6/50.66/59.92 로 달라 내부 상태 미통일.
#   같은 배속(30)에서 origin ↔ footprint 각 5회. 유효성 = fixture (A 고정 유지·도로 3개 점유) 만 —
#   B 충돌·교통 판정·도착·TIMEOUT 은 결과 지표 (flaky_post 고정 장면판). 기준 결과 전 고정. 25회 행렬 반복 아님.
cd "$(dirname "$0")/../../../.."
# 30배 STALE 수정(b1d92e3) + 막힘 에피소드(dd49272) 합친 시험 브랜치 ADAIR_wt_combo (5ab202d) — frz2 고정 장면 30배 T1 origin / T2 footprint 각 5회. 기대(결과 전 고정, Codex 2100): STALE 0/5 (둘 다), T1 REPEATED_BLOCK 유한 안전 종료 유지, T2 도착 — timeout 을 성공으로 세지 않음
S6=../ADAIR/logs/ugv/stage6; PY=../ADAIR/.venv/Scripts/python.exe; O=$S6/flaky_frz_stale
cd ADAIR_wt_combo && mkdir -p $O
echo "{\"head\": \"$(git rev-parse HEAD)\", \"dirty\": \"$(git status --porcelain --untracked-files=no | tr '\n' ' ')\", \"diag_sha1\": \"$(sha1sum $S6/flaky_diag_frz2.py | cut -c1-40)\", \"post_sha1\": \"$(sha1sum $S6/flaky_post.py | cut -c1-40)\", \"frozen_a\": [3945.123, 5561.727, 226.42]}" > $O/manifest.json
run() { mkdir -p $O/$1; UGV_BLOCK_AVOID=$2 PYTHONIOENCODING=utf-8 timeout 3000 $PY $S6/flaky_diag_frz2.py 5 $O/$1 --frozen-a 3945.123 5561.727 226.42 $3 > $O/$1/diag.out 2>&1; echo "$1 rc=$? $(grep DIAG_SUMMARY $O/$1/diag.out)"; PYTHONIOENCODING=utf-8 $PY $S6/flaky_post.py $O/$1 > $O/$1/post.out 2>&1; echo "  $(grep POST_SUMMARY $O/$1/post.out | cut -c1-400)"; }
{
run T1_origin_x30 origin ""
run T2_footprint_x30 footprint ""
} > $O/summary.txt 2>&1
echo "CHAIN_SIMFRZSTALE_DONE $(date) $(tr '\n' ' ' < $O/summary.txt | cut -c1-900)"
