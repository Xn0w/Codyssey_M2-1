# -*- coding: utf-8 -*-
"""원본 judge_corner.json (실행 폴더, 수정하지 않음) vs judge_corner_v2 출력 (v2/judge) 비교표. 사용: python -X utf8 v2_compare.py <접두어...>
출력: v2/compare_<접두어>.json 과 표 (stdout)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEYS = ("entry_ok", "apex_ok", "arc_vs_plan_ok")


def main():
    pre = sys.argv[1:] or ["r20_", "fixv_"]
    rows, agg = [], {}
    for p in pre:
        for d in sorted(HERE.glob(p + "*")):
            if not d.is_dir():
                continue
            o = json.loads((d / "judge_corner.json").read_text(encoding="utf-8"))
            vf = sorted((HERE / "v2" / "judge").glob(d.name + "__*.json"))
            if not vf:
                continue
            v = json.loads(vf[0].read_text(encoding="utf-8"))
            assert v["plan"] == o["plan"], (d.name, v["plan"], o["plan"])
            for oc, vc in zip(o["corners"], v["corners"]):
                r = {"run": d.name, "corner": oc["corner"], "tol_orig": o["tolerance"]["value_mps"], "tol_v2": v["tolerance"]["value_mps"],
                     "R_orig": oc["r_min_m"], "R_v2": vc["v2"]["R_m"], "s_orig": oc["s_m"], "s_v2": vc["v2"]["s_m"],
                     "apex_s_orig": oc["s_apex_m"], "apex_s_v2": vc["v2"]["s_apex_m"],
                     "repro_old": all(oc[k] == vc["old"][k] for k in KEYS)
                     and abs(oc["v_entry_max_mps"] - vc["old"]["v_entry_max_mps"]) <= 0.006
                     and abs(oc["v_apex_max_mps"] - vc["old"]["v_apex_max_mps"]) <= 0.006
                     and abs(oc["arc_max_over_plan_mps"] - vc["old"]["arc_max_over_plan_mps"]) <= 0.006}
                for tag, src in (("orig", oc), ("r_only", vc["r_only"]), ("win_only", vc["win_only"]), ("v2", vc["v2"])):
                    for k in KEYS:
                        r[f"{tag}.{k}"] = src[k]
                    r[f"{tag}.v_entry"] = src["v_entry_max_mps"]
                    r[f"{tag}.v_apex"] = src["v_apex_max_mps"]
                    r[f"{tag}.over_plan"] = src["arc_max_over_plan_mps"]
                r["v2.over_vcurve"] = vc["v2"]["arc_max_over_vcurve_mps"]
                r["v2.v_curve"] = vc["v2"]["v_curve_mps"]
                rows.append(r)
                g = agg.setdefault((p, oc["corner"]), {"n": 0, **{f"{t}.{k}_fail": 0 for t in ("orig", "r_only", "win_only", "v2") for k in KEYS},
                                                       "repro_old": 0})
                g["n"] += 1
                g["repro_old"] += r["repro_old"]
                for t in ("orig", "r_only", "win_only", "v2"):
                    for k in KEYS:
                        g[f"{t}.{k}_fail"] += r[f"{t}.{k}"] is False
    out = {"rows": rows, "agg": {f"{k[0]}corner{k[1]}": v for k, v in agg.items()}}
    (HERE / "v2" / f"compare_{'_'.join(x.strip('_') for x in pre)}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, g in out["agg"].items():
        print(k, json.dumps(g, ensure_ascii=False))
    print("tol 변화:", sorted({(r["run"], r["tol_orig"], r["tol_v2"]) for r in rows if r["tol_orig"] != r["tol_v2"]}))
    for r in rows:
        if not r["repro_old"]:
            print("재현 불일치", r["run"], r["corner"], r["orig.v_entry"], r["orig.v_apex"], r["orig.over_plan"])


if __name__ == "__main__":
    main()
