#!/usr/bin/env bash
# 후보 c1 정지 재현 (기준 terrain_ab/seamC/SEAMC_criteria.md, Codex 0920): cR0a → cR0b → cR1a → 멈춤·보고.
cd "$(dirname "$0")/../../.."
SC=logs/ugv/stage6/terrain_ab/seamC; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR; WS=$W/$SC; OUT=$WS/runs
[ "$(git -C ../ADAIR_wt_vehicle rev-parse --short HEAD)" = 48f3e5f ] || { echo "CHAIN_SEAMC_HOLD 차량 HEAD 불일치"; exit 0; }
(cd $SC && sha1sum -c --quiet SEAMC_freeze.sha1) || { echo "CHAIN_SEAMC_HOLD 동결 해시 불일치"; exit 0; }
mkdir -p $SC/runs
S_R0a="4400.0,5928.044,29.027,-2.5652"; S_R0b="4360.0,5928.044,29.118,-2.5652"; S_R1a="4380.6959,5928.044,29.027,-2.5652"   # = seamR/spawn_calc.json
echo "CHAIN_SEAMC_START $(date)"
one() {
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec env VEHICLE_TREE_COMMIT=48f3e5f bash $WS/seam_static_c1.sh $OUT "$1:$2:30" >> $SC/run.out 2>&1
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $WS/seam_check_c1.py $W/logs/ugv/stage5/tiles_v2 $OUT $1 R0 "$3" > $SC/runs/check_$1.out 2>&1
  local S=$(head -1 $SC/runs/check_$1.out | awk '{print $2}'); echo "SEAMC_RESULT $1 $S $(date +%T)" >> $SC/run.out; echo $S
}
S=$(one sc_R0a $S_R0a T05_16); [ "$S" = PASS ] || { echo "CHAIN_SEAMC_DONE $(date) cR0a $S — 중단"; exit 0; }
S=$(one sc_R0b $S_R0b T04_16); [ "$S" = PASS ] || { echo "CHAIN_SEAMC_DONE $(date) cR0b $S — 중단"; exit 0; }
S=$(one sc_R1a $S_R1a "T04_16|T05_16"); echo "CHAIN_SEAMC_DONE $(date) cR0a PASS, cR0b PASS, cR1a $S — 보고 (R2 는 별도 동결)"
