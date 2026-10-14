#!/usr/bin/env bash
# 후보 c1 R2 저속 통과 1회 (기준 terrain_ab/seamC/SEAMC_R2_criteria.md). 진입 = cR0a/cR0b/cR1a PASS 확인.
cd "$(dirname "$0")/../../.."
SC=logs/ugv/stage6/terrain_ab/seamC; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR; WS=$W/$SC; OUT=$WS/runs
for t in sc_R0a sc_R0b sc_R1a; do [ "$(head -1 $SC/runs/check_$t.out | awk '{print $2}')" = PASS ] || { echo "CHAIN_SEAMC_R2_HOLD $t 비PASS"; exit 0; }; done
[ "$(git -C ../ADAIR_wt_vehicle rev-parse --short HEAD)" = 48f3e5f ] || { echo "CHAIN_SEAMC_R2_HOLD 차량 HEAD 불일치"; exit 0; }
(cd $SC && sha1sum -c --quiet SEAMC_R2_freeze.sha1) || { echo "CHAIN_SEAMC_R2_HOLD 동결 해시 불일치"; exit 0; }
echo "CHAIN_SEAMC_R2_START $(date)"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec env VEHICLE_TREE_COMMIT=48f3e5f bash $WS/seam_drive_c1.sh $OUT "sc_R2:4386.0,5928.044,29.037,-2.5652:40" >> $SC/run.out 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $WS/r2_check.py $W/logs/ugv/stage5/tiles_v2 $OUT sc_R2 > $SC/runs/r2check_sc_R2.out 2>&1
S=$(head -1 $SC/runs/r2check_sc_R2.out | awk '{print $2}'); echo "SEAMC_RESULT sc_R2 $S $(date +%T)" >> $SC/run.out
echo "CHAIN_SEAMC_R2_DONE $(date) sc_R2 $S — 보고 (자동 후속 없음)"
