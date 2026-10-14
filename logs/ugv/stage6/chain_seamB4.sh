#!/usr/bin/env bash
# B 단계 (Codex 0940 2절 B·1020): 4 타일 후보 (T15_05·T16_05·T15_06·T16_06 충돌 size 보정, seamB4/tiles_c1b4) — 기준 terrain_ab/seamB4/SEAMB4_criteria.md.
# 순서: bR0 (T16_05 안) → bR1y (앞바퀴 둘 Y 경계) → bR1c (FL 네 타일 모서리) → bR2y (Y 방향 1 m/s 통과). 각 회차: 수집 끝·출력 확인 → 판정 → 비PASS/누락이면 멈춤.
cd "$(dirname "$0")/../../.."
SB=logs/ugv/stage6/terrain_ab/seamB4; SC=logs/ugv/stage6/terrain_ab/seamC; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR; WB=$W/$SB; OUT=$WB/runs
[ "$(git -C ../ADAIR_wt_vehicle rev-parse --short HEAD)" = 48f3e5f ] || { echo "CHAIN_SEAMB4_HOLD 차량 HEAD 불일치"; exit 0; }
(cd $SB && sha1sum -c --quiet SEAMB4_freeze.sha1) || { echo "CHAIN_SEAMB4_HOLD 동결 해시 불일치"; exit 0; }
mkdir -p $SB/runs
P=$(../ADAIR/.venv/Scripts/python.exe -c "import json;d=json.load(open('$SB/b4_spawn_calc.json'));print(' '.join(d['cases'][k]['spawn'] for k in ('bR0','bR1y','bR1c','bR2y_start')))"); set -- $P; S0=$1; S1Y=$2; S1C=$3; S2=$4
echo "CHAIN_SEAMB4_START $(date) bR0=$S0 bR1y=$S1Y bR1c=$S1C bR2y=$S2"
st() {  # tag spawn tiles
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec env VEHICLE_TREE_COMMIT=48f3e5f bash $WB/seam_static_b4.sh $OUT "$1:$2:30" >> $SB/run.out 2>&1
  [ -f $SB/runs/$1_meta.json ] && [ -f $SB/runs/$1.csv ] || { echo "SEAMB4_RESULT $1 MISSING_OUTPUT $(date +%T)" >> $SB/run.out; echo MISSING_OUTPUT; return; }
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$SC/seam_check_c1.py $W/logs/ugv/stage5/tiles_v2 $OUT $1 R0 "$3" > $SB/runs/check_$1.out 2>&1
  [ -f $SB/runs/check_$1.json ] || { echo "SEAMB4_RESULT $1 NO_JUDGE $(date +%T)" >> $SB/run.out; echo NO_JUDGE; return; }
  local S=$(head -1 $SB/runs/check_$1.out | awk '{print $2}'); echo "SEAMB4_RESULT $1 $S $(date +%T)" >> $SB/run.out; echo $S
}
S=$(st b4_R0 $S0 T16_05); [ "$S" = PASS ] || { echo "CHAIN_SEAMB4_DONE $(date) bR0 $S — 중단"; exit 0; }
S=$(st b4_R1y $S1Y "T16_05|T16_06"); [ "$S" = PASS ] || { echo "CHAIN_SEAMB4_DONE $(date) bR1y $S — 중단"; exit 0; }
S=$(st b4_R1c $S1C "T15_05|T16_05|T15_06|T16_06"); [ "$S" = PASS ] || { echo "CHAIN_SEAMB4_DONE $(date) bR1c $S — 중단"; exit 0; }
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec env VEHICLE_TREE_COMMIT=48f3e5f bash $WB/seam_drive_b4.sh $OUT "b4_R2y:$S2:40" >> $SB/run.out 2>&1
if [ -f $SB/runs/b4_R2y_meta.json ] && [ -f $SB/runs/b4_R2y_drive.csv ]; then
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $WB/r2_check_y.py $W/logs/ugv/stage5/tiles_v2 $OUT b4_R2y > $SB/runs/r2check_b4_R2y.out 2>&1
  S=$(head -1 $SB/runs/r2check_b4_R2y.out | awk '{print $2}'); [ -f $SB/runs/r2check_b4_R2y.json ] || S=NO_JUDGE
else S=MISSING_OUTPUT; fi
echo "SEAMB4_RESULT b4_R2y $S $(date +%T)" >> $SB/run.out
echo "CHAIN_SEAMB4_DONE $(date) bR0/bR1y/bR1c PASS, bR2y $S — 보고 (자동 후속 없음)"
