"""chain_xslope 첫 쌍 게이트 v2 (2026-10-13 Codex 답변 opus_message_reply_1423 반영 — v1 은 주행 전에 교체 — v1 실행 기록 없음).
UGV_SPEED_TERRAIN(±구간 속도 명령) 이 계획만 바꾸고 PX4 가 따르지 않으면 반복 비교는 의미가 없다. 같은 사례 off/on road_test 기록
(ADAIR_wt_integ/logs/ugv/<tag>_<stamp>.json + 같은 이름 .csv = Gazebo 자세)으로 판정한다. 기준은 주행 전 고정.

1. 기록 유효: 두 회차 모두 JSON·궤적 CSV 존재, 경로 계획 항목 있음, 마지막 지점 5 m 안 도착. 상세 기록(detail_check)은 속도 판정과 분리 — detail_evidence_ok 로만 표시 (v2.1, 답변 1436).
2. 경로 대응: off/on 계획 지점 수가 같고 같은 번호 지점이 2 m 안 — 아니면 '비교 불가' (인덱스 직접 비교 금지).
3. 낮춘 구간: on 계획이 off 보다 TOL 이상 낮은 지점 k. 공통 Item 속도 = 'k 로 가는 구간' 속도 → 창 = 경로 누적거리 (s[k-1], s[k]].
4. 제한 필요: off 실측 창 최대 속도 > on 계획 + TOL 인 창만 판별 대상. 없으면 '이 사례로 전달 효과 판별 불가' (전달 실패로도 단정 안 함).
5. 추종: 판별 대상 창에서 on 실측 창 최대 ≤ on 계획 + TOL. 꼭짓점(지점 k 최근접 표본)만 맞고 창 안에서 초과하면 apex_only 로 따로 표시.
   창 안 표본 간격 > 0.5 s 이거나 표본 3개 미만이면 그 창은 기록 부족 (HOLD).
판정: PROCEED = 판별 대상 창 ≥ 1 이고 모두 추종 / HOLD_NOT_FOLLOWED = '구동 명령 전달 미검증' / INCONCLUSIVE = 계획 변화 없음·판별 불가 /
      INVALID = 기록·경로 대응·표본 문제. chain 은 JSON 의 verdict 를 직접 읽는다."""
import csv
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INTEG = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "ADAIR_wt_integ"))
LOG = os.path.join(INTEG, "logs", "ugv")
sys.path.insert(0, INTEG)
TOL = 0.3
MATCH_M = 2.0
ARRIVE_M = 5.0
GAP_S = 0.5


def frame():
    from ugv.geo import FRAME
    return FRAME


def speeds(rows, half_s=0.25):        # road_test.speeds 와 같은 방식 (Gazebo 자세 차분)
    t = [r["sim_t"] for r in rows]
    out, j0, j1 = [], 0, 0
    for i in range(len(rows)):
        while t[i] - t[j0] > half_s:
            j0 += 1
        j1 = max(j1, i)
        while j1 + 1 < len(rows) and t[j1 + 1] - t[i] <= half_s:
            j1 += 1
        dt = t[j1] - t[j0]
        out.append(math.hypot(rows[j1]["x"] - rows[j0]["x"], rows[j1]["y"] - rows[j0]["y"]) / dt if dt > 0 else 0.0)
    return out


def load(tag):
    fs = sorted(f for f in glob.glob(os.path.join(LOG, f"{tag}_2*.json")))
    if not fs:
        return {"error": f"{tag}: 기록 JSON 없음"}
    jf = fs[-1]
    cf = jf[:-5] + ".csv"
    d = json.load(open(jf, encoding="utf-8"))
    runs = d.get("runs") or []
    run = next((r for r in runs if (r.get("route") or {}).get("items")), None)
    if run is None:
        return {"error": f"{tag}: 계획 항목 없음", "file": jf}
    if not os.path.exists(cf):
        return {"error": f"{tag}: 궤적 CSV 없음", "file": jf}
    rows = []
    with open(cf, newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({"sim_t": float(r["sim_t"]), "x": float(r["x"]), "y": float(r["y"])})
            except (TypeError, ValueError, KeyError):
                pass
    t0 = run.get("sim_t_cmd") or (rows[0]["sim_t"] if rows else 0)
    rows = [r for r in rows if r["sim_t"] >= t0]
    if len(rows) < 10:
        return {"error": f"{tag}: 명령 뒤 궤적 표본 부족", "file": jf}
    F = frame()
    items = run["route"]["items"]
    xy = [F.to_xy(i["lat"], i["lon"]) for i in items]
    an = (((d.get("analysis") or {}).get("runs") or {}).get(run["key"])) or {}
    end = an.get("end_to_last_item_m")
    chk = os.path.join(HERE, "xslope", f"{tag}_detail_check.json")
    detail = json.load(open(chk, encoding="utf-8")) if os.path.exists(chk) else None
    return {"file": jf, "csv": cf, "items_v": [i["speed_mps"] for i in items], "xy": xy, "rows": rows, "spd": speeds(rows),
            "end_to_last_item_m": end, "detail_valid": None if detail is None else detail.get("valid")}


def project(xy, cum, x, y):
    best = (1e18, 0.0)
    for i in range(len(xy) - 1):
        (ax, ay), (bx, by) = xy[i], xy[i + 1]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
        dd = math.hypot(x - ax - u * dx, y - ay - u * dy)
        if dd < best[0]:
            best = (dd, cum[i] + u * math.sqrt(L2))
    return best[1]


def track_s(run, xy, cum):
    """표본별 경로 누적거리 — 앞으로만 진행하도록 단조 보정 (교차·되돌아오는 경로의 오투영 방지)."""
    out, last = [], 0.0
    for r in run["rows"]:
        s = project(xy, cum, r["x"], r["y"])
        last = max(last, s) if s - last < 30.0 else last    # 30 m 넘는 도약은 오투영으로 보고 무시
        out.append(last)
    return out


def window(run, ss, lo, hi):
    idx = [i for i, s in enumerate(ss) if lo < s <= hi]
    if len(idx) < 3:
        return None
    ts = [run["rows"][i]["sim_t"] for i in idx]
    return {"n": len(idx), "max_gap_s": round(max(b - a for a, b in zip(ts, ts[1:])), 3),
            "max_mps": round(max(run["spd"][i] for i in idx), 2), "idx": idx}


def main(off_tag, on_tag, out):
    res = {"gate_version": "xslope_gate v2.1", "off": off_tag, "on": on_tag, "tol_mps": TOL}
    off, on = load(off_tag), load(on_tag)

    def done(verdict, reason, **kw):
        res.update(verdict=verdict, proceed=verdict == "PROCEED", reason=reason, **kw)
        json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("XSLOPE_GATE", verdict, reason)
        return 0

    errs = [r["error"] for r in (off, on) if "error" in r]
    if errs:
        return done("INVALID", "; ".join(errs))
    res.update(off_file=off["file"], on_file=on["file"], end_to_last_item_m=[off["end_to_last_item_m"], on["end_to_last_item_m"]],
               detail_valid=[off["detail_valid"], on["detail_valid"]])
    if any(e is None or e > ARRIVE_M for e in res["end_to_last_item_m"]):
        return done("INVALID", f"도착 미확인 (마지막 지점 {ARRIVE_M:g} m 밖 또는 값 없음)")
    # 속도 판단과 상세(하중·롤) 판단 분리 (Codex 답변 1436): 상세 증거는 valid is True 일 때만 유효 — 이 게이트 판정에는 쓰지 않고 표시만
    res["detail_evidence_ok"] = all(v is True for v in res["detail_valid"])
    res["detail_note"] = "상세 하중·롤 비교는 detail_evidence_ok=true 회차만. 상세 CSV 핵심 구간 최대 간격은 아직 미확인 (남은 한계)"
    if len(off["xy"]) != len(on["xy"]):
        return done("INVALID", f"경로 대응 불가 — 계획 지점 수 다름 (off {len(off['xy'])}, on {len(on['xy'])})")
    dmax = max(math.dist(a, b) for a, b in zip(off["xy"], on["xy"]))
    res["item_xy_max_diff_m"] = round(dmax, 2)
    if dmax > MATCH_M:
        return done("INVALID", f"경로 대응 불가 — 같은 번호 지점 거리 {dmax:.1f} m > {MATCH_M:g} m")
    xy = on["xy"]
    cum = [0.0]
    for a, b in zip(xy, xy[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    lowered = [k for k in range(1, len(xy)) if on["items_v"][k] <= off["items_v"][k] - TOL]
    res["plan_items_off"], res["plan_items_on"], res["lowered_items"] = off["items_v"], on["items_v"], lowered
    if not lowered:
        return done("INCONCLUSIVE", "후보가 이 사례 계획을 바꾸지 않음 (on 이 off 보다 0.3 m/s 이상 낮은 지점 없음)")
    s_off, s_on = track_s(off, xy, cum), track_s(on, xy, cum)
    wins = []
    for k in lowered:
        lo, hi = cum[k - 1], cum[k]
        wo, wn = window(off, s_off, lo, hi), window(on, s_on, lo, hi)
        w = {"item": k, "s_window_m": [round(lo, 1), round(hi, 1)], "plan_off": off["items_v"][k], "plan_on": on["items_v"][k]}
        if wo is None or wn is None or wo["max_gap_s"] > GAP_S or wn["max_gap_s"] > GAP_S:
            w["status"] = "RECORD_GAP"
            w["samples"] = [None if x is None else {"n": x["n"], "max_gap_s": x["max_gap_s"]} for x in (wo, wn)]
            wins.append(w)
            continue
        w.update(off_actual_max=wo["max_mps"], on_actual_max=wn["max_mps"], samples=[wo["n"], wn["n"]], max_gap_s=[wo["max_gap_s"], wn["max_gap_s"]])
        if wo["max_mps"] <= w["plan_on"] + TOL:
            w["status"] = "NOT_NEEDED"          # off 도 이미 새 제한 안 — 판별 불가
        else:
            ap = min(wn["idx"], key=lambda i: math.dist((on["rows"][i]["x"], on["rows"][i]["y"]), xy[k]))
            w["on_apex_mps"] = round(on["spd"][ap], 2)
            if wn["max_mps"] <= w["plan_on"] + TOL:
                w["status"] = "FOLLOWED"
            elif w["on_apex_mps"] <= w["plan_on"] + TOL:
                w["status"] = "APEX_ONLY"       # 꼭짓점만 준수, 진입 구간 초과
            else:
                w["status"] = "NOT_FOLLOWED"
        wins.append(w)
    res["windows"] = wins
    st = [w["status"] for w in wins]
    res["window_counts"] = {k: st.count(k) for k in ("FOLLOWED", "APEX_ONLY", "NOT_FOLLOWED", "NOT_NEEDED", "RECORD_GAP")}
    if "RECORD_GAP" in st:
        return done("INVALID", "낮춘 구간 기록 부족 (표본 3개 미만 또는 간격 > 0.5 s)")
    judged = [w for w in wins if w["status"] != "NOT_NEEDED"]
    if not judged:
        return done("INCONCLUSIVE", "이 사례로 전달 효과 판별 불가 — off 도 낮춘 구간에서 이미 on 계획 이하")
    if all(w["status"] == "FOLLOWED" for w in judged):
        return done("PROCEED", "제한이 필요한 구간에서 on 실측이 on 계획을 따름")
    return done("HOLD_NOT_FOLLOWED", "구동 명령 전달 미검증 — 제한이 필요한 구간에서 on 실측이 계획 초과 (APEX_ONLY 포함)")


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
