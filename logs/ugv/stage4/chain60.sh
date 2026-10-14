#!/usr/bin/env bash
# 2026-10-13 chain59 INVALID_RECORD 2회 재시험 (같은 조건: wt_fix 서버, susp_a0, D8, STALL_DETECT=1). 원본 회차: road_test 결과 JSON 미기록 (TypeError hex() 예외 1, 무출력 종료 1)
#  A: susp_a0 · D8 · STALL_DETECT=1 — chain53 과 같은 32 사례 (정상 회전에서 오감지 없음 확인)
#  B: susp_a0 · D8 · STALL_DETECT=0 — 같은 서버 대조, 사례마다 1회 (16) — 서버 변경 효과와 플래그 효과 구분
#  C: base(원본+접촉 센서) · D8 — 경유점 놓침 자연 재현(chain53 3/3) j494943·j495073: STALL_DETECT=1 각 3회, =0 각 2회 (고장 감지·정지·추가 이탈)
# 안전 정지 성공은 임무 성공으로 세지 않는다. 기동 run_sc_v5 (서버 기능 증거 server_evidence_<TAG>.json, 실제 해석 증거 prov_<TAG>.json, 정지 검사).
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v5.sh; ST=$M/logs/ugv/stage5; J=logs/ugv/stage5/jturn
until grep -q CHAIN_FT2_DONE logs/ugv/stage6/chain_ft2.out 2>/dev/null; do sleep 20; done
SUB=$ST/tiles_v2/road_subset_all_included.json
export SERVER_TREE=ADAIR_wt_fix
run() {  # SERVER_TREE 를 앞에 주면 그 회차만 다른 서버  # 후보 STALL 태그 타일 월드 스폰 fleet rid inst target
  local VAR=$1 SD=$2; shift 2
  UGV_MODEL_VARIANT=$VAR UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=$SD PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $4 $5 bash -c "cd ../ADAIR_wt_fix && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 120 --post-stop-s 15 --world $3"
}
run susp_a0 1 c59Ar_j495663_1400_0021_D8_susp0_stall1_ctlb_r1 tiles_v2_D8all wj495663_1400_0021 $J/j495663_1400_0021_D8_spawn.txt $J/j495663_1400_0021_fleet.json B-ugv1 3 RP:683400021:20.0
run susp_a0 1 c59Ar_j494873_0793_1375_D8_susp0_stall1_ctla_r1 tiles_v2_D8all wj494873_0793_1375 $J/j494873_0793_1375_D8_spawn.txt $J/j494873_0793_1375_fleet.json A-ugv1 1 RP:682501375:20.0
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN60_DONE $(date)"
