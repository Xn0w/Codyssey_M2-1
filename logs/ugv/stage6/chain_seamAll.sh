#!/usr/bin/env bash
# 전 타일 보정 월드 (tiles_v2c1) 주행·정차 진단 4 회 (기준 terrain_ab/seamAll/SEAMALL_criteria.md): a1 X 경계 반대 방향 → a2 X 경계 45° → a3 Y 정확 경계 15 s 정차 후 재출발 → a4 네 타일 모서리 정지.
# 진단 묶음: 판정 FAIL 이어도 다음 회차 진행, 단 표식 (abort·invalid·contaminated)·출력 누락이면 멈춤.
cd "$(dirname "$0")/../../.."
SA=logs/ugv/stage6/terrain_ab/seamAll; SC=logs/ugv/stage6/terrain_ab/seamC; SB=logs/ugv/stage6/terrain_ab/seamB4; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR; WA=$W/$SA; OUT=$WA/runs; TL=$W/logs/ugv/stage5/tiles_v2c1
[ "$(git -C ../ADAIR_wt_vehicle rev-parse --short HEAD)" = 48f3e5f ] || { echo "CHAIN_SEAMALL_HOLD 차량 HEAD"; exit 0; }
(cd $SA && sha1sum -c --quiet SEAMALL_freeze.sha1) || { echo "CHAIN_SEAMALL_HOLD 동결 해시"; exit 0; }
P=$(../ADAIR/.venv/Scripts/python.exe -c "import json;d=json.load(open('$SA/all_spawn_calc.json'));print(' '.join(d[k]['spawn'] for k in ('a1_revX','a2_obliqX','a3_stopY','a4_corner')))"); set -- $P; S1=$1; S2=$2; S3=$3; S4=$4
echo "CHAIN_SEAMALL_START $(date)"
ok() { [ -f $SA/runs/$1_meta.json ] && [ -f $SA/runs/$1.csv ] && [ -f "$2" ] && ../ADAIR/.venv/Scripts/python.exe -c "import json,sys;d=json.load(open(sys.argv[1],encoding='utf-8'));sys.exit(0 if not d.get('markers') else 1)" "$2"; }
drv() {  # tag spawn settle drive axis bnd dir from to
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec env VEHICLE_TREE_COMMIT=48f3e5f R2_SETTLE=$3 R2_DRIVE=$4 bash $WA/seam_drive_all.sh $OUT "$1:$2:$(( $3 + $4 + 20 ))" >> $SA/run.out 2>&1
  [ -f $SA/runs/$1_meta.json ] && [ -f $SA/runs/$1_drive.csv ] || { echo "SEAMALL_RESULT $1 MISSING_OUTPUT $(date +%T)" >> $SA/run.out; echo STOP; return; }
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec env AXIS=$5 BND=$6 DIR=$7 TFROM=$8 TTO=$9 AABB500=160 AABB499=0 python3 $WA/r2_check_gen.py $TL $OUT $1 > $SA/runs/r2check_$1.out 2>&1
  local S=$(head -1 $SA/runs/r2check_$1.out | awk '{print $2}'); echo "SEAMALL_RESULT $1 $S $(date +%T)" >> $SA/run.out
  ok $1 $SA/runs/r2check_$1.json && echo $S || echo STOP
}
R=$(drv a1_revX $S1 5 15 x 4380 1 T04_16 T05_16); [ "$R" = STOP ] && { echo "CHAIN_SEAMALL_DONE $(date) a1 멈춤"; exit 0; }
R=$(drv a2_obliqX $S2 5 18 x 4380 1 T04_16 T05_16); [ "$R" = STOP ] && { echo "CHAIN_SEAMALL_DONE $(date) a2 멈춤"; exit 0; }
R=$(drv a3_stopY $S3 15 10 y -4631 1 T16_ T16_06); [ "$R" = STOP ] && { echo "CHAIN_SEAMALL_DONE $(date) a3 멈춤"; exit 0; }
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec env VEHICLE_TREE_COMMIT=48f3e5f bash $WA/seam_static_all.sh $OUT "a4_corner:$S4:30" >> $SA/run.out 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/$SB/seam_check_c1b.py $TL $OUT a4_corner R0 "T15_05|T16_05|T15_06|T16_06" > $SA/runs/check_a4_corner.out 2>&1
S=$(head -1 $SA/runs/check_a4_corner.out | awk '{print $2}'); echo "SEAMALL_RESULT a4_corner $S $(date +%T)" >> $SA/run.out
echo "CHAIN_SEAMALL_DONE $(date) 4 회 끝 — 보고"
