#!/usr/bin/env bash
# 타일 경계 정지 재현 (기준 terrain_ab/seamR/SEAMR_criteria.md, Codex 0905): R0a → PASS 면 R0b → PASS 면 R1a → 멈춤·보고. 자동 R1b/R2 없음.
cd "$(dirname "$0")/../../.."
SR=logs/ugv/stage6/terrain_ab/seamR; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR; WS=$W/$SR; OUT=$WS/runs
[ "$(git -C ../ADAIR_wt_vehicle rev-parse --short HEAD)" = 48f3e5f ] || { echo "CHAIN_SEAMR_HOLD 차량 HEAD 불일치"; exit 0; }
(cd $SR && sha1sum -c --quiet SEAMR_freeze.sha1) || { echo "CHAIN_SEAMR_HOLD 동결 해시 불일치"; exit 0; }
mkdir -p $SR/runs
P=$(python -c "import json;d=json.load(open('$SR/spawn_calc.json'));print(' '.join(d['cases'][k]['spawn'] for k in ('R0a','R0b','R1a')))" 2>/dev/null || ../ADAIR/.venv/Scripts/python.exe -c "import json;d=json.load(open('$SR/spawn_calc.json'));print(' '.join(d['cases'][k]['spawn'] for k in ('R0a','R0b','R1a')))")
set -- $P; S_R0a=$1; S_R0b=$2; S_R1a=$3
echo "CHAIN_SEAMR_START $(date) R0a=$S_R0a R0b=$S_R0b R1a=$S_R1a"
one() {  # tag spawn kind tile
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec env VEHICLE_TREE_COMMIT=48f3e5f bash $WS/seam_static.sh $OUT "$1:$2:30" >> $SR/run.out 2>&1
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $WS/seam_check.py $W/logs/ugv/stage5/tiles_v2 $OUT $1 $3 $4 > $SR/runs/check_$1.out 2>&1
  local S=$(head -1 $SR/runs/check_$1.out | awk '{print $2}'); echo "SEAMR_RESULT $1 $S $(date +%T)" >> $SR/run.out; echo $S
}
S=$(one sr_R0a $S_R0a R0 T05_16); [ "$S" = PASS ] || { echo "CHAIN_SEAMR_DONE $(date) R0a $S — R1 안 함"; exit 0; }
S=$(one sr_R0b $S_R0b R0 T04_16); [ "$S" = PASS ] || { echo "CHAIN_SEAMR_DONE $(date) R0b $S — R1 안 함"; exit 0; }
S=$(one sr_R1a $S_R1a R1 ""); echo "CHAIN_SEAMR_DONE $(date) R0a PASS, R0b PASS, R1a $S — 보고 (R1b/R2 자동 없음)"
