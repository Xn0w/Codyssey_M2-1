# -*- coding: utf-8 -*-
"""sweep120 eval 결과 집계 → agg120.json + 표"""
import json, math, statistics as st
from pathlib import Path
W = Path(__file__).parent
C = ("base", "fix1", "fix12", "cand")
NAME = {"base": "기준(HEAD)", "fix1": "수정1", "fix12": "수정1+2", "cand": "수정1+2+원호상한"}
BINS = [(0, 15), (15, 25), (25, 40), (40, 60.01)]
out = {}
for lat in ("1.0", "1.5"):
    E = {c: json.loads((W / f"eval_{c}_lat{lat}.json").read_text(encoding="utf-8"))["rows"] for c in C}
    assert all(len(E[c]) == 120 and all(r["pts_same"] for r in E[c]) for c in C)
    res = {}
    for c in C:
        def pct(key):
            r = [E[c][i][key] / E["base"][i][key] - 1 for i in range(120)]
            r.sort()
            return {"mean_%": round(100 * st.mean(r), 2), "median_%": round(100 * st.median(r), 2),
                    "p95_%": round(100 * r[int(0.95 * 119)], 2), "max_%": round(100 * max(r), 2), "min_%": round(100 * min(r), 2)}
        def absv(key):
            r = sorted(x[key] for x in E[c])
            return {"mean": round(st.mean(r), 2), "median": round(st.median(r), 2), "p95": round(r[int(0.95 * 119)], 2), "max": round(max(r), 2)}
        bins = {}
        for lo, hi in BINS:
            po = [a["plan_over"] for x in E[c] for a in x["arcs"] if lo <= a["R"] < hi]
            io = [a["item_over"] for x in E[c] for a in x["arcs"] if lo <= a["R"] < hi and a["item_over"] is not None]
            bins[f"R{lo}-{int(hi)}"] = {"n_arcs": len(po), "plan_over_max": round(max(po), 3) if po else None,
                                        "n_plan_over_gt_0.05": sum(1 for v in po if v > 0.05),
                                        "item_over_max": round(max(io), 3) if io else None,
                                        "n_item_over_gt_0.05": sum(1 for v in io if v > 0.05)}
        res[c] = {"name": NAME[c], "eta_plan_s": absv("eta_plan"), "eta_plan_vs_base": pct("eta_plan"),
                  "eta_items_s": absv("eta_items"), "eta_items_vs_base": pct("eta_items"),
                  "n_items": absv("n_items"), "min_item_v": absv("min_item_v"),
                  "n_items_total": sum(x["n_items"] for x in E[c]), "min_item_v_min": min(x["min_item_v"] for x in E[c]),
                  "arc_over_by_R": bins, "n_gen_arcs_total": sum(x["n_gen_arcs"] for x in E[c])}
    out[f"lat{lat}"] = res
(W / "agg120.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for lat, res in out.items():
    print("==", lat)
    for c, r in res.items():
        print(r["name"], "ETA계획 s", r["eta_plan_s"], "대비", r["eta_plan_vs_base"])
        print("   ETA항목 s", r["eta_items_s"], "대비", r["eta_items_vs_base"], "항목수합", r["n_items_total"], "최소항목속도", r["min_item_v_min"])
        print("   ", json.dumps(r["arc_over_by_R"], ensure_ascii=False))
