#!/usr/bin/env bash
# run_sc_v6 가 서버 준비 뒤 실행: (WSL) gz_detail 상세 기록(바퀴 접촉력·서스펜션) 백그라운드 + (Windows) ADAIR_wt_integ road_test. 환경 D_* 는 체인이 준다.
#   D_TAG D_WORLD D_MODEL(adair_ugv_N) D_RID D_TARGET D_TILES(절대) D_SUB(절대)   (stage4/detail_cmd.sh 의 통합 트리·stage6/xslope 판)
# 2026-10-13 Codex 검토: 기록기 rc·meta 저장 (rc 3 = 이 스크립트가 보낸 SIGTERM 으로 예상된 중단, 0 = 200 s 완주, 그 밖 = 기록 무효),
#   종료 신호는 이번 출력 파일 이름으로만 좁힘, 상세 CSV 가 road_test 궤적 구간을 덮는지 확인해 <tag>_detail_check.json 에 남김.
cd "$(dirname "$0")/../../.."
V=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle
R=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR
OUT="$R/logs/ugv/stage6/xslope/${D_TAG}_detail.csv"
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --cd "$V" --exec env GZ_PARTITION=adair_ugv GZ_IP=127.0.0.1 python3 -m ugv.tools.gz_detail --world "$D_WORLD" --model "$D_MODEL" --out "$OUT" --duration 200 > "logs/ugv/stage6/xslope/${D_TAG}_detail.log" 2>&1 &
REC=$!
sleep 2
( cd ../ADAIR_wt_integ && env UGV_LAT_ACCEL=1.0 UGV_ROAD_SUBSET="$D_SUB" ADAIR_TILES_OUT="$D_TILES" ../ADAIR/.venv/Scripts/python.exe -m ugv.tools.road_test --tag "$D_TAG" --rid "$D_RID" --model "$D_MODEL" --target-node "$D_TARGET" --track-s 150 --post-stop-s 35 --world "$D_WORLD" )
RC=$?
SENT=0
if kill -0 $REC 2>/dev/null; then
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec pkill -TERM -f "ugv.tools.gz_detail .*--out $OUT"; SENT=1
fi
wait $REC; RRC=$?
echo "detail_rc=$RRC sigterm_sent=$SENT" >> "logs/ugv/stage6/xslope/${D_TAG}_detail.log"
TRK=$(ls -t ../ADAIR_wt_integ/logs/ugv/${D_TAG}_*.csv 2>/dev/null | head -1)
.venv/Scripts/python.exe - "logs/ugv/stage6/xslope/${D_TAG}_detail.csv" "$TRK" "$RRC" "$SENT" <<'PY'
import csv, json, sys
det, trk, rrc, sent = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4] == "1"
def span(p):
    try:
        with open(p, encoding="utf-8") as f:
            t = [float(r["sim_t"]) for r in csv.DictReader(f) if r.get("sim_t") not in (None, "", "nan")]
        return (min(t), max(t), len(t)) if t else None
    except Exception as e:  # noqa: BLE001
        return None
d, k = span(det), span(trk) if trk else None
cover = None
if d and k:
    lo, hi = max(d[0], k[0]), min(d[1], k[1])
    cover = round(max(0.0, hi - lo) / max(k[1] - k[0], 1e-6), 3)
rc_ok = rrc == 0 or (rrc == 3 and sent)
res = {"detail_rc": rrc, "sigterm_sent": sent, "rc_ok": rc_ok, "rc_basis": "0 완주 / 3 은 이 스크립트 SIGTERM 일 때만 예상 중단 / 그 밖 무효",
       "detail_span": d, "track_csv": trk, "track_span": k, "coverage_of_track": cover,
       "valid": bool(rc_ok and cover is not None and cover >= 0.98)}
open(det[:-4] + "_check.json", "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
print("detail_check", json.dumps({x: res[x] for x in ("detail_rc", "sigterm_sent", "coverage_of_track", "valid")}, ensure_ascii=False))
PY
exit $RC
