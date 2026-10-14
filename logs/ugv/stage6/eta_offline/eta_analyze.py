"""ETA 상한 오프라인 분석 (Fable 미해결 5.1) — eta_dump_plugin 의 JSONL 을 읽어 격자별 선택을 다시 계산한다.
사용: python eta_analyze.py <dump.jsonl> <out.json>
선택 규칙은 approach._plan_once (e839eee) 를 그대로 옮김: improving(목표에 IMPROVE_M 이상 가까워짐) 최소 도착 = t_best,
cap = max(ratio·t_best, t_best + extra), 모두 빠지면 상한 무시, near_set(≤ NEAR_M, 없으면 25 m 단위 최근접), 기준 + max(SLACK_S, SLACK_RATIO·기준) 안에서
(round(d/25), t) 최소. 현재 값(3, 600)으로 다시 계산한 선택이 덤프된 실제 선택과 같은지 먼저 검사 (재현 실패면 분석 무효)."""
import json
import math
import sys
from collections import Counter

IMPROVE_M, NEAR_M, SLACK_S, SLACK_R = 100.0, 1000.0, 60.0, 0.25
RATIOS = [2, 2.5, 3, 4, 5, math.inf]
EXTRAS = [300, 450, 600, 900, math.inf]
CUR = (3, 600)


def select(rec, ratio, extra):
    ok = rec["ok"]
    tx, ty = rec["target_xy"]
    sx, sy = rec["start_xy"]
    d_start = math.hypot(sx - tx, sy - ty)
    imp = [o[3] for o in ok if o[2] <= d_start - IMPROVE_M]
    t_best = min(imp) if imp else None
    cap = math.inf if t_best is None else max(ratio * t_best if ratio != math.inf else math.inf, t_best + extra)
    kept = [o for o in ok if o[3] <= cap]
    out_n = len(ok) - len(kept)
    if not kept:
        kept, out_n = ok, len(ok)       # 원래 코드: capped_out == len(ok) 이면 거르지 않음
    near = [o for o in kept if o[2] <= NEAR_M]
    fallback = not near
    if not near:
        dmin = min(o[2] for o in kept)
        near = [o for o in kept if round(o[2] / 25.0) <= round(dmin / 25.0)]
    t_ref = min(o[3] for o in near)
    limit = t_ref + max(SLACK_S, SLACK_R * t_ref)
    ch = min((o for o in kept if o[3] <= limit), key=lambda o: (round(o[2] / 25.0), o[3]))
    return {"chosen": ch, "t_best": t_best, "capped_out": out_n, "fallback": fallback, "d_start": d_start,
            "chosen_improving": ch[2] <= d_start - IMPROVE_M}


def main():
    rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
    errs = [r for r in rows if r["kind"] == "dump_error"]
    cands = [r for r in rows if r["kind"] == "cands"]
    chosen = {r["seq"]: r for r in rows if r["kind"] == "chosen"}
    recs, mism = [], []
    for c in cands:
        if c["fixed_dest"] or not c["ok"]:
            continue
        nxt = chosen.get(c["seq"] + 1)
        cur = select(c, *CUR)
        if nxt is not None and [nxt["chosen"][0], nxt["chosen"][1]] != [cur["chosen"][0], cur["chosen"][1]]:
            mism.append({"seq": c["seq"], "test": c["test"], "dump": nxt["chosen"], "recomputed": cur["chosen"]})
        unc = select(c, math.inf, math.inf)
        tb = unc["t_best"]
        recs.append({"seq": c["seq"], "test": c["test"], "n_ok": len(c["ok"]), "t_best": tb,
                     "uncapped_choice": unc["chosen"], "uncapped_ratio": None if not tb else round(unc["chosen"][3] / tb, 3),
                     "uncapped_extra_s": None if tb is None else round(unc["chosen"][3] - tb, 1),
                     "current_choice": cur["chosen"], "current_capped_out": cur["capped_out"], "fallback_near": cur["fallback"],
                     "current_choice_improving": cur["chosen_improving"],
                     "grid": {f"{r}|{e}": select(c, r, e)["chosen"][:2] for r in RATIOS for e in EXTRAS}})
    grid = {}
    for r in RATIOS:
        for e in EXTRAS:
            k = f"{r}|{e}"
            diff = [x for x in recs if x["grid"][k] != x["current_choice"][:2]]
            grid[k] = {"differs_from_current": len(diff), "tests": sorted({x["test"] for x in diff})[:20]}
    bounded = [x for x in recs if x["t_best"]]
    affected = [x for x in bounded if x["uncapped_choice"][:2] != x["current_choice"][:2]]
    near_band = [x for x in bounded if x["uncapped_ratio"] and (2.4 <= x["uncapped_ratio"] <= 3.6 or 480 <= (x["uncapped_extra_s"] or 0) <= 720)
                 and x["uncapped_choice"][:2] != [None, None]]
    res = {"dump": sys.argv[1], "rows": len(rows), "dump_errors": len(errs), "cands_records": len(cands), "analysed": len(recs),
           "replay_mismatch": mism[:20], "replay_mismatch_n": len(mism),
           "cap_affects_choice_n": len(affected),
           "cap_affects_choice": [{k: x[k] for k in ("seq", "test", "t_best", "uncapped_choice", "uncapped_ratio", "uncapped_extra_s", "current_choice")} for x in affected],
           "uncapped_ratio_hist": Counter(None if x["uncapped_ratio"] is None else round(x["uncapped_ratio"], 1) for x in bounded).most_common(30),
           "within_20pct_of_threshold_n": len(near_band),
           "within_20pct_of_threshold": [{k: x[k] for k in ("seq", "test", "uncapped_ratio", "uncapped_extra_s")} for x in near_band][:30],
           "fallback_near_n": sum(x["fallback_near"] for x in recs),
           "fallback_near_not_improving_n": sum(x["fallback_near"] and not x["current_choice_improving"] for x in recs),
           "grid": grid}
    json.dump(res, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("rows", "dump_errors", "analysed", "replay_mismatch_n", "cap_affects_choice_n",
                                          "within_20pct_of_threshold_n", "fallback_near_n", "fallback_near_not_improving_n")}, ensure_ascii=False))
    print({k: v["differs_from_current"] for k, v in grid.items()})


main()
