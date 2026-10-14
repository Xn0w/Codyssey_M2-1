#!/usr/bin/env bash
# B 정확-경계 v3 재기록 1 회 (Codex 1055 1절, 기준 terrain_ab/seamB4/SEAMB4E_criteria.md): 원 bR1y 와 같은 배치·조건, 바뀐 것 = 기록기 v3 (점별 원본) 만. 원인 진단 — PASS 여도 원 FAIL 취소 안 함.
cd "$(dirname "$0")/../../.."
SB=logs/ugv/stage6/terrain_ab/seamB4; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR; WB=$W/$SB; OUT=$WB/runs; T=b4e_exact
[ "$(git -C ../ADAIR_wt_vehicle rev-parse --short HEAD)" = 48f3e5f ] || { echo "CHAIN_SEAMB4E_HOLD 차량 HEAD 불일치"; exit 0; }
(cd $SB && sha1sum -c --quiet SEAMB4E_freeze.sha1) || { echo "CHAIN_SEAMB4E_HOLD 동결 해시 불일치"; exit 0; }
echo "CHAIN_SEAMB4E_START $(date)"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec env VEHICLE_TREE_COMMIT=48f3e5f bash $WB/seam_static_b4d.sh $OUT "$T:15400.8,-4632.35,101.992,1.570796:30" >> $SB/run_e.out 2>&1
[ -f $SB/runs/${T}_meta.json ] && [ -f $SB/runs/$T.csv ] && [ -f $SB/runs/${T}_raw.jsonl ] || { echo "CHAIN_SEAMB4E_DONE $(date) MISSING_OUTPUT"; exit 0; }
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $WB/seam_check_c1b.py $W/logs/ugv/stage5/tiles_v2 $OUT $T R0 "T16_05|T16_06" > $SB/runs/check_$T.out 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $WB/raw_check_v2.py $OUT $T > $SB/runs/rawcheck_$T.out 2>&1
[ -f $SB/runs/check_$T.json ] && [ -f $SB/runs/rawcheck_$T.json ] || { echo "CHAIN_SEAMB4E_DONE $(date) NO_JUDGE"; exit 0; }
S=$(head -1 $SB/runs/check_$T.out | awk '{print $2}'); echo "SEAMB4E_RESULT $T $S $(date +%T)" >> $SB/run_e.out
echo "CHAIN_SEAMB4E_DONE $(date) $T $S — 보고 (자동 후속 없음)"
