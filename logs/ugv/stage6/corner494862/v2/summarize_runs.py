# -*- coding: utf-8 -*-
"""v2/runs/<tag> 판정·집계 (시험 도구). 각 실행의 계획 = 그 실행 서버가 돌려준 route_final.json (실제 실린 계획).
사용: python summarize_runs.py <tag> [--tol-exclude old|v2]  → v2/judge/<tag>.json, 한 줄 요약 출력 (criteria_frozen.json 기준)"""
import json, re, subprocess, sys, csv
from pathlib import Path
H = Path(__file__).resolve().parent
PY = sys.executable
tag = sys.argv[1]; tx = sys.argv[3] if len(sys.argv) > 3 else "old"
O = H / "runs" / tag
plan = O / "route_final.json"
outj = H / "judge" / f"{tag}.json"
subprocess.run([PY, "-X", "utf8", str(H.parent / "judge_corner_v2.py"), str(O), str(plan), "--lat", "1.0", "--out", str(outj), "--tol-exclude", tx],
               check=True, capture_output=True)
J = json.loads(outj.read_text(encoding="utf-8"))
P = json.loads(plan.read_text(encoding="utf-8"))
rt = (O / "road_test.out").read_text(encoding="utf-8", errors="replace")
g = lambda pat: (m.group(1) if (m := re.search(pat, rt)) else None)
out_n = g(r'"body_outside_est_road\(samples\)": (\d+)'); end_m = g(r'"end_to_last_item_m": ([\d.]+)')
# ulog 마지막 구간 실린 속도
last_carried = None
us = O / "ulog_speed.csv"
if us.exists():
    vals = [float(r["cruising_speed"]) for r in csv.DictReader(open(us, newline="")) if r["kind"] == "triplet" and r["lat"] not in ("nan", "") and float(r["cruising_speed"]) > 0]
    last_carried = vals[-1] if vals else None
arcs = []
for c in J["corners"]:
    w = c.get("v2")
    if w:
        arcs.append({"id": f"c{c['corner']}", **{k: w[k] for k in ("R_m", "v_curve_mps", "v_entry_max_mps", "v_apex_max_mps", "arc_max_over_plan_mps", "arc_max_over_vcurve_mps", "entry_ok", "apex_ok", "arc_vs_plan_ok", "arc_vs_vcurve_ok")}})
man = json.loads((O / "manifest.json").read_text(encoding="utf-8"))
src_arcs = P.get("plan_arcs")
if src_arcs is None and man.get("case") not in (None, "corner"):      # 대조(원호 정보 없는 트리): 같은 선형의 후보 계획 원호 정보로 교차로 원호 위치만 찾는다
    src_arcs = json.loads((H / "cases" / man["case"] / "plan_cand.json").read_text(encoding="utf-8")).get("plan_arcs")
junc = [a for a in (src_arcs or []) if a["kind"] == "junction"]
for c in J["extra_arcs"]:
    w = c["v2"]
    if any(min(j["s1"], w["s_m"][1]) - max(j["s0"], w["s_m"][0]) > 1.0 for j in junc):
        arcs.append({"id": "junction", **{k: w[k] for k in ("R_m", "v_curve_mps", "v_entry_max_mps", "v_apex_max_mps", "arc_max_over_plan_mps", "arc_max_over_vcurve_mps", "entry_ok", "apex_ok", "arc_vs_plan_ok", "arc_vs_vcurve_ok")}})
t = J.get("task") or {}
res = {"tag": tag, "manifest": json.loads((O / "manifest.json").read_text(encoding="utf-8")).get("server_tree"),
       "ready": (O / "ready.txt").read_text().strip(), "susp": (O / "model_check.txt").read_text().strip(),
       "result": f'{t.get("status")}/{t.get("mission_result")}', "fault": (J.get("final") or {}).get("fault"),
       "out_n": None if out_n is None else int(out_n), "end_m": None if end_m is None else float(end_m), "tol": J["tolerance"]["value_mps"],
       "items_plan": [i["speed_mps"] for i in P["items"]], "last_item_plan": P["items"][-1]["speed_mps"], "last_carried": last_carried,
       "px4": (O / "px4_params.txt").read_text().strip() if (O / "px4_params.txt").exists() else None,
       "leftover": (O / "leftover.txt").read_text().strip() if (O / "leftover.txt").exists() else None, "arcs": arcs}
ok = (res["result"] == "COMPLETED/ARRIVED" and res["fault"] is None and res["out_n"] == 0 and res["end_m"] is not None and res["end_m"] <= 1.0
      and all(a[k] is True for a in arcs for k in ("entry_ok", "apex_ok", "arc_vs_plan_ok", "arc_vs_vcurve_ok")) and len(arcs) > 0
      and res["last_carried"] is not None and abs(res["last_carried"] - res["last_item_plan"]) <= 0.011)
res["PASS"] = ok
(H / "judge" / f"{tag}__summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False))
