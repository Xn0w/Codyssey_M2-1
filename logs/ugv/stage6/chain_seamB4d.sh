#!/usr/bin/env bash
# B 단계 별도 진단 2 회 (Codex 1045 2절, 기준 terrain_ab/seamB4/SEAMB4D_criteria.md): 앞차축 y 만 +0.10 (bD_N) → −0.10 (bD_S). 원 B 체인 재개 아님.
# ft/fn 정적 FAIL 만이면 (계측 유효·표식/중단 없음·NO_MSG 없음) 반대쪽까지 수행, 그 밖의 이상이면 멈춤.
cd "$(dirname "$0")/../../.."
SB=logs/ugv/stage6/terrain_ab/seamB4; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR; WB=$W/$SB; OUT=$WB/runs
[ "$(git -C ../ADAIR_wt_vehicle rev-parse --short HEAD)" = 48f3e5f ] || { echo "CHAIN_SEAMB4D_HOLD 차량 HEAD 불일치"; exit 0; }
(cd $SB && sha1sum -c --quiet SEAMB4D_freeze.sha1) || { echo "CHAIN_SEAMB4D_HOLD 동결 해시 불일치"; exit 0; }
echo "CHAIN_SEAMB4D_START $(date)"
dg() {  # tag spawn
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec env VEHICLE_TREE_COMMIT=48f3e5f bash $WB/seam_static_b4d.sh $OUT "$1:$2:30" >> $SB/run_d.out 2>&1
  [ -f $SB/runs/$1_meta.json ] && [ -f $SB/runs/$1.csv ] && [ -f $SB/runs/$1_raw.jsonl ] || { echo "SEAMB4D_RESULT $1 MISSING_OUTPUT $(date +%T)" >> $SB/run_d.out; echo MISSING_OUTPUT; return; }
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $WB/seam_check_c1b.py $W/logs/ugv/stage5/tiles_v2 $OUT $1 R0 "T16_05|T16_06" > $SB/runs/check_$1.out 2>&1
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $WB/raw_check.py $OUT $1 > $SB/runs/rawcheck_$1.out 2>&1
  [ -f $SB/runs/check_$1.json ] && [ -f $SB/runs/rawcheck_$1.json ] || { echo "SEAMB4D_RESULT $1 NO_JUDGE $(date +%T)" >> $SB/run_d.out; echo NO_JUDGE; return; }
  local S=$(head -1 $SB/runs/check_$1.out | awk '{print $2}')
  local ONLY=$(../ADAIR/.venv/Scripts/python.exe -c "import json;c=json.load(open('$SB/runs/check_$1.json'))['checks'];m=json.load(open('$SB/runs/check_$1.json'))['markers'];bad=[k for k,v in c.items() if v is not True];print('FTFN_ONLY' if bad==['ft_fn_ratio_le_0.1'] and not m else ('OK' if not bad and not m else 'OTHER'))")
  echo "SEAMB4D_RESULT $1 $S $ONLY $(date +%T)" >> $SB/run_d.out; echo "$S $ONLY"
}
R=$(dg b4d_N 15400.8,-4632.25,101.992,1.570796); set -- $R; [ "$2" = OK ] || [ "$2" = FTFN_ONLY ] || { echo "CHAIN_SEAMB4D_DONE $(date) bD_N $R — 멈춤"; exit 0; }
R2=$(dg b4d_S 15400.8,-4632.45,101.993,1.570796)
echo "CHAIN_SEAMB4D_DONE $(date) bD_N $R / bD_S $R2 — 보고 (자동 후속 없음)"
