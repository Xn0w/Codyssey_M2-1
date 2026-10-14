#!/usr/bin/env bash
# 2026-10-13 개선 2종 비교 (사용자 지시: fire_v2b 검증 뒤, 별도 변경으로 적용 전후 비교). chain_slope3 뒤에. 통합 트리 서버 (정체 감지 켬).
#   후보 UGV_SPEED_TERRAIN (하강 경사·불리 횡경사 속도 계획, ead59da) — off / on 각 3회. 정지 후보(dc91f13)는 chain_slope3 에서 따로.
#   사례: 횡경사 회전 s1592_down·s1096_up·s1096_down (slope2), 5.5 % 내리막 도착 s0547_down (slope). gz_detail 로 바퀴 하중·롤 기록.
#   비교: 차체 도로 이탈(judge3)·롤·바퀴 하중(최소/축 평균)·도착 시간·실제 정지점·정지 유지. 판정 기준은 기존 그대로.
cd "$(dirname "$0")/../../.."
until grep -q CHAIN_SLOPE3_DONE logs/ugv/stage6/chain_slope3.out 2>/dev/null; do sleep 30; done
# 답변 1436 재시도 보완(wip/integ-s5-next)을 slope3 가 끝난 뒤에만 통합 트리에 반영 (slope3 실행 중 코드 불변)
git -C ../ADAIR_wt_integ merge -q --ff-only wip/integ-s5-next || { echo "CHAIN_XSLOPE_HOLD $(date) 통합 트리 ff 병합 실패 — 시험 안 함"; echo "CHAIN_XSLOPE_DONE $(date) (보류)"; exit 0; }
(cd ../ADAIR_wt_integ && PYTHONIOENCODING=utf-8 timeout 600 ../ADAIR/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider ugv/tests/test_speed_cmd.py ugv/tests/test_terrain_speed.py; echo "rc=$?") > logs/ugv/stage6/xslope_pretest.txt 2>&1
git -C ../ADAIR_wt_integ rev-parse HEAD >> logs/ugv/stage6/xslope_pretest.txt
git -C ../ADAIR_wt_integ merge-base --is-ancestor 47690ba HEAD && echo "contains_47690ba=yes" >> logs/ugv/stage6/xslope_pretest.txt
grep -q "^rc=0$" logs/ugv/stage6/xslope_pretest.txt && grep -q "contains_47690ba=yes" logs/ugv/stage6/xslope_pretest.txt || { echo "CHAIN_XSLOPE_HOLD $(date) 사전 단위 시험 실패"; echo "CHAIN_XSLOPE_DONE $(date) (보류)"; exit 0; }
M=$(pwd); RT=logs/ugv/stage4/run_sc_v6.sh; ST=$M/logs/ugv/stage5
SUB=$ST/tiles_v2/road_subset_all_included.json
export UGV_MODEL_VARIANT=susp_a SERVER_TREE=ADAIR_wt_integ
run() {   # tag casedir case world rid inst target extra_env
  env $8 UGV_PX4_PASS_SKIP=0 UGV_PX4_STALL_DETECT=1 PF_SKIP_SUBSET=1 SUBSET=$SUB TILES=tiles_v2 WORLD=$4 UGV_LAT_ACCEL=1.0 \
    D_TAG=$1 D_WORLD=$4 D_MODEL=adair_ugv_$6 D_RID=$5 D_TARGET=$7 D_TILES=$ST/tiles_v2 D_SUB=$SUB \
    bash $RT $1 logs/ugv/stage6/$2/$3_spawn.txt logs/ugv/stage6/$2/$3_fleet.json bash logs/ugv/stage6/detail_cmd_x.sh
}
# 비교 밖 후보는 명시적으로 고정 (Codex 검토). 3 모드: off / on (계획만 — 미션 항목 속도로만 전달) / cmd (계획 + 구간 속도 명령 UGV_SPEED_TERRAIN_CMD, 9c49f69)
OFF="UGV_SPEED_TERRAIN=0 UGV_SPEED_TERRAIN_CMD=0 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0"
ON="UGV_SPEED_TERRAIN=1 UGV_SPEED_TERRAIN_CMD=0 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_TERRAIN_TILES=$ST/tiles_v2"
CMD="UGV_SPEED_TERRAIN=1 UGV_SPEED_TERRAIN_CMD=1 UGV_STOP_SPEED_CMD=0 UGV_STOP_GRADE=0 UGV_TERRAIN_TILES=$ST/tiles_v2"
mkdir -p logs/ugv/stage6/xslope
(cd ../ADAIR_wt_integ && git rev-parse HEAD) > logs/ugv/stage6/xslope/integ_head.txt
(cd ../ADAIR_wt_integ && PYTHONIOENCODING=utf-8 ../ADAIR/.venv/Scripts/python.exe -c "from ugv import terrain_speed as T, vehicle as V; import json; d={k: getattr(T, k) for k in dir(T) if k.isupper() and isinstance(getattr(T, k), (int, float, str))}; d.update({k: getattr(V, k) for k in ('SPEED_CMD_DELTA', 'SPEED_CMD_MIN_S')}); print(json.dumps(d))") > logs/ugv/stage6/xslope/constants.json 2>&1
case_run() {   # mode rep case
  E=$OFF; [ $1 = on ] && E=$ON; [ $1 = cmd ] && E=$CMD
  case $3 in
    s1592_down) run xs$1_s1592_down_$2 slope2 s1592_down wj494866_0722_1925 A-ugv1 1 RP:682501592:84.2 "$E" ;;
    s1096_up)   run xs$1_s1096_up_$2 slope2 s1096_up wj495663_1400_0021 B-ugv1 3 RP:683501096:256.0 "$E" ;;
    s1096_down) run xs$1_s1096_down_$2 slope2 s1096_down wj495663_1400_0021 B-ugv1 3 RP:683501096:10.0 "$E" ;;
    s0547_down) run xs$1_s0547_down_$2 slope s0547_down wj495731_0574_0583 B-ugv1 3 RP:683400547:165.9 "$E" ;;
  esac
}
G=logs/ugv/stage6/xslope
{
# 첫 쌍 게이트 v2 (Codex 답변 1423): 횡경사 곡선(s1096_down)·하강 직선(s0547_down) 각 off/on/cmd 1회 → xslope_gate.py (기준 주행 전 고정).
#   off-on = 미션 항목 속도만으로 전달되는지 기록, off-cmd = 진행 판단. 판단은 JSON verdict 를 직접 읽는다 (문자열 검색 아님).
#   진행 = cmd 게이트에 PROCEED ≥ 1 이고 HOLD_NOT_FOLLOWED·INVALID·파일 없음 0. INCONCLUSIVE(판별 불가)는 실패로 세지 않지만 진행 근거도 아님.
for c in s1096_down s0547_down; do case_run off a $c; case_run on a $c; case_run cmd a $c; done
for c in s1096_down s0547_down; do for m in on cmd; do
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe logs/ugv/stage6/xslope_gate.py xsoff_${c}_a xs${m}_${c}_a $G/gate_${m}_${c}.json; echo "gate $m $c rc=$?"
done; done
DEC=$(.venv/Scripts/python.exe - <<'EOF'
import json, os
G = "logs/ugv/stage6/xslope"
v = {}
for c in ("s1096_down", "s0547_down"):
    f = f"{G}/gate_cmd_{c}.json"
    try:
        v[c] = json.load(open(f, encoding="utf-8")).get("verdict") or "NO_VERDICT"
    except Exception as e:  # noqa: BLE001
        v[c] = f"READ_FAIL"
ok = any(x == "PROCEED" for x in v.values()) and not any(x in ("HOLD_NOT_FOLLOWED", "INVALID", "READ_FAIL", "NO_VERDICT") for x in v.values())
json.dump({"cmd_verdicts": v, "proceed": ok, "rule": "PROCEED>=1 and no HOLD_NOT_FOLLOWED/INVALID/READ_FAIL"}, open(f"{G}/first_pair_decision.json", "w", encoding="utf-8"), ensure_ascii=False)
print("PROCEED" if ok else "HOLD", json.dumps(v))
EOF
)
echo "first_pair $DEC"
if [ "${DEC%% *}" != PROCEED ]; then
  echo "CHAIN_XSLOPE_HOLD $(date) 첫 쌍 게이트 보류 — 반복 안 함: $DEC"
else
  for c in s1592_down s1096_up; do case_run off a $c; case_run cmd a $c; done
  for rep in b c; do for c in s1592_down s1096_up s1096_down s0547_down; do case_run off $rep $c; case_run cmd $rep $c; done; done
fi
} > logs/ugv/stage6/xslope_runs.out 2>&1
grep -h "CHAIN_XSLOPE_HOLD" logs/ugv/stage6/xslope_runs.out
echo "CHAIN_XSLOPE_DONE $(date)"
