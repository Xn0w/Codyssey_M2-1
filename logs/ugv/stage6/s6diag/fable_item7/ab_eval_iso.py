# -*- coding: utf-8 -*-
"""s6diag/ab_eval.py 와 같은 4 쌍 정적 평가 — 격리 후보(iso_patch) 적용 여부를 argv[3] ('iso' | 'none') 로. cwd = 트리.
python ab_eval_iso.py <tiles> <out.json> iso|none"""
import asyncio, json, os, pathlib, sys, tempfile, hashlib
tiles = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2]); mode = sys.argv[3]
os.environ["UGV_ROAD_SUBSET"] = str(tiles / "road_subset_all_included.json"); os.environ.setdefault("UGV_ALLOW_NO_FIRE_DATA", "1")
sys.path.insert(0, ".")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
iso = None
if mode == "iso":
    import iso_patch as iso
from ugv.roads import RoadNetwork
import ugv.tests.test_multi_vehicle as tm
from ugv.tests.test_multi_vehicle import FLEET_CFG, make_fleet
from ugv.approach import node_id_of
net = RoadNetwork(); tm.NET = net
cfg = {c["resource_id"]: c for c in FLEET_CFG}


def fleet(rid):
    f, _ = make_fleet(pathlib.Path(tempfile.mkdtemp()), [cfg[rid]]); return f.vehicles[rid]


res = {"tiles": str(tiles), "mode": mode, "iso_deg": getattr(iso, "ISO_DEG", None),
       "git_head": os.popen("git rev-parse HEAD").read().strip(), "pairs": {}}
for src, dst in [("A-ugv1", "B-ugv1"), ("B-ugv1", "A-ugv1"), ("A-fire1", "B-fire1"), ("B-fire1", "A-fire1")]:
    if iso:
        iso.FILTERED.clear(); iso.APPLIED.clear()
    Vs, Vd = fleet(src), fleet(dst)
    body = {"task_id": "AB", "decision_id": "AB", "target_node": node_id_of(Vd.access)}
    ev = asyncio.run(Vs.evaluate(body))
    apd = ev.get("approach") or {}
    row = {"vehicle": Vs.profile.name, "planner": ev["verdict"], "reason": ev.get("detail") or ev.get("reason"), "eta_s": ev.get("eta_sec"),
           "approach_mode": apd.get("mode"), "dist_to_target_m": apd.get("dist_to_target_m")}
    if ev["verdict"] == "ACCEPT":
        try:
            asyncio.run(Vs.execute(body))
            pl = Vs.plan
            rc = (pl.detail or {}).get("route_check") or {}
            row.update(route_km=round(pl.route.cum[-1] / 1000, 2) if hasattr(pl.route, "cum") else round(Vs.speed.cum[-1] / 1000, 2),
                       route_roads=len(pl.route.road_ids), route_check_ok=rc.get("ok"),
                       route_check={k: rc.get(k) for k in ("steering_violations", "body_violations", "worst_excess_m") if k in rc},
                       junction_relax={k: pl.detail.get(k) for k in ("junction_joins_relaxed", "junction_joins_relaxed_long", "junction_arc_omitted") if pl.detail.get(k)},
                       rejected=(pl.detail or {}).get("route_check_rejected"),
                       turn_variants=[[str(x[0])] + [round(v, 2) for v in x[1:]] for x in (getattr(pl.route, "turn_variants", None) or [])],
                       road_ids=list(pl.route.road_ids))
        except Exception as e:  # noqa: BLE001
            row["execute_error"] = repr(e)[:400]
    if iso:
        row["iso_filtered_level3"] = sorted({(str(p), m) for p, m in iso.FILTERED})
        row["iso_applied_level3"] = sorted({(str(p), m) for p, m in iso.APPLIED})
    res["pairs"][f"{src}->{dst}"] = row
    print(f"{src}->{dst}", json.dumps({k: v for k, v in row.items() if k != "road_ids"}, ensure_ascii=False, default=str)[:900], flush=True)
out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
