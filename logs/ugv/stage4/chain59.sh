#!/usr/bin/env bash
# 2026-10-12 차량 개조 P4 (재설계, 독립 검증 P1 반영): 정체 감지 UGV_PX4_STALL_DETECT·MISSION_STALL 은 ADAIR_wt_fix 서버에만 있다 → 서버 SERVER_TREE=ADAIR_wt_fix (5ffb41a) 로 통일.
#  A: susp_a0 · D8 · STALL_DETECT=1 — chain53 과 같은 32 사례 (정상 회전에서 오감지 없음 확인)
#  B: susp_a0 · D8 · STALL_DETECT=0 — 같은 서버 대조, 사례마다 1회 (16) — 서버 변경 효과와 플래그 효과 구분
#  C: base(원본+접촉 센서) · D8 — 경유점 놓침 자연 재현(chain53 3/3) j494943·j495073: STALL_DETECT=1 각 3회, =0 각 2회 (고장 감지·정지·추가 이탈)
# 안전 정지 성공은 임무 성공으로 세지 않는다. 기동 run_sc_v5 (서버 기능 증거 server_evidence_<TAG>.json, 실제 해석 증거 prov_<TAG>.json, 정지 검사).
cd "$(dirname "$0")/../../.."
M=$(pwd); PY=$M/.venv/Scripts/python.exe; RT=logs/ugv/stage4/run_sc_v5.sh; ST=$M/logs/ugv/stage5; J=logs/ugv/stage5/jturn
until grep -q CHAIN58_DONE logs/ugv/stage4/chain58.out 2>/dev/null; do sleep 15; done
SUB=$ST/tiles_v2/road_subset_all_included.json
export SERVER_TREE=ADAIR_wt_fix
run() {  # SERVER_TREE 를 앞에 주면 그 회차만 다른 서버  # 후보 STALL 태그 타일 월드 스폰 fleet rid inst target
  local VAR=$1 SD=$2; shift 2
  UGV_MODEL_VARIANT=$VAR UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=$SD PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=$2 WORLD=$3 UGV_LAT_ACCEL=1.0 bash $RT $1 $4 $5 bash -c "cd ../ADAIR_wt_fix && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET=$SUB ADAIR_TILES_OUT=$ST/$2 $PY -m ugv.tools.road_test --tag $1 --rid $6 --model adair_ugv_$7 --target-node $8 --track-s 120 --post-stop-s 15 --world $3"
}
run base 1 c59C_j494943_1351_1352_D8_base_stall1_a tiles_v2_D8all wj494943_1351_1352 $J/j494943_1351_1352_D8_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
# 관문 (독립 검증 요청): 첫 고장 유도 회차에서 MISSION_STALL 발생·실제 정지를 확인한 뒤에만 이어간다 — 확인되면 logs/ugv/stage4/c59_GATE_OK 를 만든다
touch logs/ugv/stage4/c59_GATE_WAIT; echo "관문 대기 $(date)"
until [ -f logs/ugv/stage4/c59_GATE_OK ] || [ -f logs/ugv/stage4/c59_GATE_ABORT ]; do sleep 10; done
[ -f logs/ugv/stage4/c59_GATE_ABORT ] && { echo "관문 중단 $(date)"; echo "CHAIN59_DONE (중단) $(date)"; exit 1; }
run susp_a0 1 c59A_j494846_1237_1921_D8_susp0_stall1_a tiles_v2_D8all wj494846_1237_1921 $J/j494846_1237_1921_D8_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run susp_a0 1 c59A_j494846_1237_1921_D8_susp0_stall1_b tiles_v2_D8all wj494846_1237_1921 $J/j494846_1237_1921_D8_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run susp_a0 1 c59A_j494846_1237_1921_D8_susp0_stall1_c tiles_v2_D8all wj494846_1237_1921 $J/j494846_1237_1921_D8_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run susp_a0 1 c59A_j495759_0730_0731_D8_susp0_stall1_a tiles_v2_D8all wj495759_0730_0731 $J/j495759_0730_0731_D8_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run susp_a0 1 c59A_j495759_0730_0731_D8_susp0_stall1_b tiles_v2_D8all wj495759_0730_0731 $J/j495759_0730_0731_D8_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run susp_a0 1 c59A_j495759_0730_0731_D8_susp0_stall1_c tiles_v2_D8all wj495759_0730_0731 $J/j495759_0730_0731_D8_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run susp_a0 1 c59A_j494866_0722_1925_D8_susp0_stall1_a tiles_v2_D8all wj494866_0722_1925 $J/j494866_0722_1925_D8_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run susp_a0 1 c59A_j494866_0722_1925_D8_susp0_stall1_b tiles_v2_D8all wj494866_0722_1925 $J/j494866_0722_1925_D8_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run susp_a0 1 c59A_j494866_0722_1925_D8_susp0_stall1_c tiles_v2_D8all wj494866_0722_1925 $J/j494866_0722_1925_D8_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run susp_a0 1 c59A_j495039_2958_3115_D8_susp0_stall1_a tiles_v2_D8all wj495039_2958_3115 $J/j495039_2958_3115_D8_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
run susp_a0 1 c59A_j495039_2958_3115_D8_susp0_stall1_b tiles_v2_D8all wj495039_2958_3115 $J/j495039_2958_3115_D8_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
run susp_a0 1 c59A_j495039_2958_3115_D8_susp0_stall1_c tiles_v2_D8all wj495039_2958_3115 $J/j495039_2958_3115_D8_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
run susp_a0 1 c59A_j494943_1351_1352_D8_susp0_stall1_a tiles_v2_D8all wj494943_1351_1352 $J/j494943_1351_1352_D8_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run susp_a0 1 c59A_j494943_1351_1352_D8_susp0_stall1_b tiles_v2_D8all wj494943_1351_1352 $J/j494943_1351_1352_D8_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run susp_a0 1 c59A_j494943_1351_1352_D8_susp0_stall1_c tiles_v2_D8all wj494943_1351_1352 $J/j494943_1351_1352_D8_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run susp_a0 1 c59A_j495731_0574_0583_D8_susp0_stall1_a tiles_v2_D8all wj495731_0574_0583 $J/j495731_0574_0583_D8_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run susp_a0 1 c59A_j495731_0574_0583_D8_susp0_stall1_b tiles_v2_D8all wj495731_0574_0583 $J/j495731_0574_0583_D8_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run susp_a0 1 c59A_j495731_0574_0583_D8_susp0_stall1_c tiles_v2_D8all wj495731_0574_0583 $J/j495731_0574_0583_D8_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run susp_a0 1 c59A_j495073_2092_2054_D8_susp0_stall1_a tiles_v2_D8all wj495073_2092_2054 $J/j495073_2092_2054_D8_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run susp_a0 1 c59A_j495073_2092_2054_D8_susp0_stall1_b tiles_v2_D8all wj495073_2092_2054 $J/j495073_2092_2054_D8_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run susp_a0 1 c59A_j495073_2092_2054_D8_susp0_stall1_c tiles_v2_D8all wj495073_2092_2054 $J/j495073_2092_2054_D8_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run susp_a0 1 c59A_j496345_0188_0778_D8_susp0_stall1_ctla tiles_v2_D8all wj496345_0188_0778 $J/j496345_0188_0778_D8_spawn.txt $J/j496345_0188_0778_fleet.json B-ugv1 3 RP:684400778:175.9
run susp_a0 1 c59A_j494990_1573_1574_D8_susp0_stall1_ctla tiles_v2_D8all wj494990_1573_1574 $J/j494990_1573_1574_D8_spawn.txt $J/j494990_1573_1574_fleet.json A-ugv1 1 RP:682501574:29.1
run susp_a0 1 c59A_j495663_1400_0021_D8_susp0_stall1_ctla tiles_v2_D8all wj495663_1400_0021 $J/j495663_1400_0021_D8_spawn.txt $J/j495663_1400_0021_fleet.json B-ugv1 3 RP:683400021:20.0
run susp_a0 1 c59A_j495663_1400_0021_D8_susp0_stall1_ctlb tiles_v2_D8all wj495663_1400_0021 $J/j495663_1400_0021_D8_spawn.txt $J/j495663_1400_0021_fleet.json B-ugv1 3 RP:683400021:20.0
run susp_a0 1 c59A_j495663_1400_0021_D8_susp0_stall1_ctlc tiles_v2_D8all wj495663_1400_0021 $J/j495663_1400_0021_D8_spawn.txt $J/j495663_1400_0021_fleet.json B-ugv1 3 RP:683400021:20.0
run susp_a0 1 c59A_j494865_0523_1574_D8_susp0_stall1_ctla tiles_v2_D8all wj494865_0523_1574 $J/j494865_0523_1574_D8_spawn.txt $J/j494865_0523_1574_fleet.json A-ugv1 1 RP:682501574:20.0
run susp_a0 1 c59A_j495794_0381_0383_D8_susp0_stall1_ctla tiles_v2_D8all wj495794_0381_0383 $J/j495794_0381_0383_D8_spawn.txt $J/j495794_0381_0383_fleet.json B-ugv1 3 RP:683500383:94.1
run susp_a0 1 c59A_j495069_2784_2074_D8_susp0_stall1_ctla tiles_v2_D8all wj495069_2784_2074 $J/j495069_2784_2074_D8_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1
run susp_a0 1 c59A_j494873_0793_1375_D8_susp0_stall1_ctla tiles_v2_D8all wj494873_0793_1375 $J/j494873_0793_1375_D8_spawn.txt $J/j494873_0793_1375_fleet.json A-ugv1 1 RP:682501375:20.0
run susp_a0 1 c59A_j495011_1875_1652_D8_susp0_stall1_ctla tiles_v2_D8all wj495011_1875_1652 $J/j495011_1875_1652_D8_spawn.txt $J/j495011_1875_1652_fleet.json A-ugv1 1 RP:682501652:43.0
run susp_a0 1 c59A_j622566_3123_3108_D8_susp0_stall1_ctla tiles_v2_D8all wj622566_3123_3108 $J/j622566_3123_3108_D8_spawn.txt $J/j622566_3123_3108_fleet.json A-ugv1 1 RP:682503108:61.0
run susp_a0 0 c59B_j494846_1237_1921_D8_susp0_stall0 tiles_v2_D8all wj494846_1237_1921 $J/j494846_1237_1921_D8_spawn.txt $J/j494846_1237_1921_fleet.json A-ugv1 1 RP:682501921:20.0
run susp_a0 0 c59B_j495759_0730_0731_D8_susp0_stall0 tiles_v2_D8all wj495759_0730_0731 $J/j495759_0730_0731_D8_spawn.txt $J/j495759_0730_0731_fleet.json B-ugv1 3 RP:683400731:55.9
run susp_a0 0 c59B_j494866_0722_1925_D8_susp0_stall0 tiles_v2_D8all wj494866_0722_1925 $J/j494866_0722_1925_D8_spawn.txt $J/j494866_0722_1925_fleet.json A-ugv1 1 RP:682501925:76.6
run susp_a0 0 c59B_j495039_2958_3115_D8_susp0_stall0 tiles_v2_D8all wj495039_2958_3115 $J/j495039_2958_3115_D8_spawn.txt $J/j495039_2958_3115_fleet.json A-ugv1 1 RP:682503115:20.0
run susp_a0 0 c59B_j494943_1351_1352_D8_susp0_stall0 tiles_v2_D8all wj494943_1351_1352 $J/j494943_1351_1352_D8_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run susp_a0 0 c59B_j495731_0574_0583_D8_susp0_stall0 tiles_v2_D8all wj495731_0574_0583 $J/j495731_0574_0583_D8_spawn.txt $J/j495731_0574_0583_fleet.json B-ugv1 3 RP:683400583:240.7
run susp_a0 0 c59B_j495073_2092_2054_D8_susp0_stall0 tiles_v2_D8all wj495073_2092_2054 $J/j495073_2092_2054_D8_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run susp_a0 0 c59B_j496345_0188_0778_D8_susp0_stall0 tiles_v2_D8all wj496345_0188_0778 $J/j496345_0188_0778_D8_spawn.txt $J/j496345_0188_0778_fleet.json B-ugv1 3 RP:684400778:175.9
run susp_a0 0 c59B_j494990_1573_1574_D8_susp0_stall0 tiles_v2_D8all wj494990_1573_1574 $J/j494990_1573_1574_D8_spawn.txt $J/j494990_1573_1574_fleet.json A-ugv1 1 RP:682501574:29.1
run susp_a0 0 c59B_j495663_1400_0021_D8_susp0_stall0 tiles_v2_D8all wj495663_1400_0021 $J/j495663_1400_0021_D8_spawn.txt $J/j495663_1400_0021_fleet.json B-ugv1 3 RP:683400021:20.0
run susp_a0 0 c59B_j494865_0523_1574_D8_susp0_stall0 tiles_v2_D8all wj494865_0523_1574 $J/j494865_0523_1574_D8_spawn.txt $J/j494865_0523_1574_fleet.json A-ugv1 1 RP:682501574:20.0
run susp_a0 0 c59B_j495794_0381_0383_D8_susp0_stall0 tiles_v2_D8all wj495794_0381_0383 $J/j495794_0381_0383_D8_spawn.txt $J/j495794_0381_0383_fleet.json B-ugv1 3 RP:683500383:94.1
run susp_a0 0 c59B_j495069_2784_2074_D8_susp0_stall0 tiles_v2_D8all wj495069_2784_2074 $J/j495069_2784_2074_D8_spawn.txt $J/j495069_2784_2074_fleet.json A-ugv1 1 RP:682502074:79.1
run susp_a0 0 c59B_j494873_0793_1375_D8_susp0_stall0 tiles_v2_D8all wj494873_0793_1375 $J/j494873_0793_1375_D8_spawn.txt $J/j494873_0793_1375_fleet.json A-ugv1 1 RP:682501375:20.0
run susp_a0 0 c59B_j495011_1875_1652_D8_susp0_stall0 tiles_v2_D8all wj495011_1875_1652 $J/j495011_1875_1652_D8_spawn.txt $J/j495011_1875_1652_fleet.json A-ugv1 1 RP:682501652:43.0
run susp_a0 0 c59B_j622566_3123_3108_D8_susp0_stall0 tiles_v2_D8all wj622566_3123_3108 $J/j622566_3123_3108_D8_spawn.txt $J/j622566_3123_3108_fleet.json A-ugv1 1 RP:682503108:61.0
run base 1 c59C_j494943_1351_1352_D8_base_stall1_b tiles_v2_D8all wj494943_1351_1352 $J/j494943_1351_1352_D8_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run base 1 c59C_j494943_1351_1352_D8_base_stall1_c tiles_v2_D8all wj494943_1351_1352 $J/j494943_1351_1352_D8_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run base 0 c59C_j494943_1351_1352_D8_base_stall0_a tiles_v2_D8all wj494943_1351_1352 $J/j494943_1351_1352_D8_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run base 0 c59C_j494943_1351_1352_D8_base_stall0_b tiles_v2_D8all wj494943_1351_1352 $J/j494943_1351_1352_D8_spawn.txt $J/j494943_1351_1352_fleet.json A-ugv1 1 RP:682501352:20.0
run base 1 c59C_j495073_2092_2054_D8_base_stall1_a tiles_v2_D8all wj495073_2092_2054 $J/j495073_2092_2054_D8_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run base 1 c59C_j495073_2092_2054_D8_base_stall1_b tiles_v2_D8all wj495073_2092_2054 $J/j495073_2092_2054_D8_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run base 1 c59C_j495073_2092_2054_D8_base_stall1_c tiles_v2_D8all wj495073_2092_2054 $J/j495073_2092_2054_D8_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run base 0 c59C_j495073_2092_2054_D8_base_stall0_a tiles_v2_D8all wj495073_2092_2054 $J/j495073_2092_2054_D8_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
run base 0 c59C_j495073_2092_2054_D8_base_stall0_b tiles_v2_D8all wj495073_2092_2054 $J/j495073_2092_2054_D8_spawn.txt $J/j495073_2092_2054_fleet.json A-ugv1 1 RP:682502054:20.0
# 96 매트릭스 무효 회차 재시험 (chain57 과 같은 조건: 서버 wt_turn·STALL_DETECT 0·susp_a0), 유효가 나올 때까지 최대 3번
for r in 1 2 3; do
  SERVER_TREE=ADAIR_wt_turn run susp_a0 0 c57r_j496345_0188_0778_D8_susp0_c$r tiles_v2_D8all wj496345_0188_0778 $J/j496345_0188_0778_D8_spawn.txt $J/j496345_0188_0778_fleet.json B-ugv1 3 RP:684400778:175.9
  grep -aq '임무:' logs/ugv/stage4/c57r_j496345_0188_0778_D8_susp0_c$r.out 2>/dev/null && break
done
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"
echo "CHAIN59_DONE $(date)"
