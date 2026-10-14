#!/usr/bin/env bash
# 2026-10-14 E4 Gazebo 4회 (기준: logs/ugv/stage6/e4/E4_criteria.md, 실행 전 고정). 서버 ADAIR_wt_hook 17a7305, run_sc_v7.
cd "$(dirname "$0")/../../.."
M=$(pwd); RT=logs/ugv/stage4/run_sc_v7.sh; ST=$M/logs/ugv/stage5; PY=../ADAIR/.venv/Scripts/python.exe
HK=../ADAIR_wt_hook; O=logs/ugv/stage6/e4; mkdir -p $O; AV=logs/ugv/stage6/av_diag
# 0) 선행 게이트: 같은 트리 전체 단위시험 (오토 모드 진단 실행). 접근 위반 등으로 결과 줄이 없으면 새 run id 로 1회 재실행
until grep -q AV_DIAG_DONE $AV/auto_hook_suite.log 2>/dev/null; do sleep 20; done
gate() { tail -1 $AV/$1/pytest.txt | grep -qE "^[0-9]+ passed in" ; }
if ! gate auto_hook_suite; then
  # 사용자 지시: 접근 위반이 반복되면 그 유형 중단 — 단위시험 재실행은 1회까지
  if tail -1 $AV/auto_hook_suite/pytest.txt | grep -q "failed"; then echo "CHAIN_E4_HOLD $(date) 단위시험 실패: $(tail -1 $AV/auto_hook_suite/pytest.txt)"; exit 0; fi
  TREE=ADAIR_wt_hook bash $AV/run_av_diag.sh auto_hook_suite2 > $AV/auto_hook_suite2.log 2>&1
  gate auto_hook_suite2 || { echo "CHAIN_E4_HOLD $(date) 단위시험 재실행도 결과 없음/실패: $(tail -1 $AV/auto_hook_suite2/pytest.txt)"; exit 0; }
fi
(cd $HK && git rev-parse HEAD > ../ADAIR/$O/head.txt)
SUB=$ST/tiles_v2/road_subset_all_included.json
export SERVER_TREE=ADAIR_wt_hook
E="UGV_PX4_END_EXTEND=1 UGV_PX4_PARK_AFTER_S=2.0 UGV_STOP_CAP_FIRST=0 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0"
# 사용자 지시 (2026-10-14 01:05): 접근 위반(래퍼 무효·중단)이 많이 나면 그런 시험을 멈추고 접근 위반 없는 작업으로. 묶음 전체 2회면 중단
BAD=0
run() {   # tag variant case world rid inst target
  [ $BAD -ge 2 ] && { echo "$1 건너뜀 — 묶음 무효/중단 $BAD 회 (사용자 지시: 접근 위반 많으면 중단)" >> $O/run.out; return; }
  local TAG=$1
  for TRY in "" _r2; do
    T=$TAG$TRY
    env $E UGV_MODEL_VARIANT=$2 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=$4 UGV_LAT_ACCEL=1.0 \
      bash $RT $T $3_spawn.txt $3_fleet.json \
      bash -c "cd $HK && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/tiles_v2 $PY -m ugv.tools.road_test --tag $T --rid $5 --model adair_ugv_$6 --target-node $7 --track-s 170 --post-stop-s 35 --world $4" >> $O/run.out 2>&1
    RC=$?
    echo "$T run rc=$RC rcfile=$(cat logs/ugv/stage4/rc_$T.json 2>/dev/null) verify=$(tail -1 logs/ugv/stage4/verify_$T.txt 2>/dev/null)" >> $O/run.out
    MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ls -t \$HOME/.adair-ugv/px4-$6/log/*/*.ulg | head -1" > $O/ulog_$T.txt 2>&1
    # 래퍼 무효(증거 3~7·사후 정지 8·접근 위반 등 시험 rc≠0 이면서 road_test 결과 없음)만 1회 재시도. 판정 실패는 재시도하지 않는다
    if [ $RC = 0 ] || grep -aq "^임무:" logs/ugv/stage4/$T.out 2>/dev/null; then break; fi
    BAD=$((BAD+1)); echo "$T 래퍼 무효/중단 (rc=$RC, 묶음 누적 $BAD)" >> $O/run.out
    [ $BAD -ge 2 ] && break
  done
}
S1=logs/ugv/stage6/slope2/s1096_down; S3=logs/ugv/stage6/slope/s3113_down
run e4_acc3_s1096_a susp_a_acc3 $S1 wj495663_1400_0021 B-ugv1 3 RP:683501096:10.0
run e4_acc3_s1096_b susp_a_acc3 $S1 wj495663_1400_0021 B-ugv1 3 RP:683501096:10.0
run e4_raoff_s1096_a susp_a $S1 wj495663_1400_0021 B-ugv1 3 RP:683501096:10.0
run e4_acc3_s3113_a susp_a_acc3 $S3 wj494846_1237_1921 A-ugv1 1 RP:682503113:143.0
PYTHONIOENCODING=utf-8 $PY logs/ugv/stage6/slope_report.py --prefix e4_ --logs $HK/logs/ugv --out $M/$O/e4_slope_report.json > $O/e4_slope_report.out 2>&1
echo "CHAIN_E4_DONE $(date) $(grep 'run rc' $O/run.out | tr '\n' ' ')"
