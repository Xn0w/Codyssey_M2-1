"""S6 정적 (읽기 전용 — road_subset 을 쓰지 않는 ab_connect 2단계 판): 차종별·방향별 계획기 evaluate → ACCEPT 면 execute 로
최종 경로·route_check(check_route) 결과·사용한 대안 원호 목록을 기록. 실행 (트리에서): python ab_eval.py <tiles> <out.json>"""
import asyncio, json, os, pathlib, sys, tempfile, hashlib
tiles = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2])
os.environ["UGV_ROAD_SUBSET"] = str(tiles / "road_subset_all_included.json"); os.environ.setdefault("UGV_ALLOW_NO_FIRE_DATA", "1")
sys.path.insert(0, ".")
from ugv.roads import RoadNetwork
import ugv.tests.test_multi_vehicle as tm
from ugv.tests.test_multi_vehicle import FLEET_CFG, make_fleet
from ugv.approach import node_id_of
net = RoadNetwork(); tm.NET = net
cfg = {c["resource_id"]: c for c in FLEET_CFG}
def fleet(rid):
    f, _ = make_fleet(pathlib.Path(tempfile.mkdtemp()), [cfg[rid]]); return f.vehicles[rid]
res = {"tiles": str(tiles), "subset_sha1": hashlib.sha1((tiles / "road_subset_all_included.json").read_bytes()).hexdigest(),
       "git_head": os.popen("git rev-parse HEAD").read().strip(),
       "git_dirty_ugv": os.popen("git status --porcelain --untracked-files=no -- ugv").read().strip() or "",   # Codex 2100: 출처 장부
       "tiles_json_sha1": hashlib.sha1((tiles / "tiles.json").read_bytes()).hexdigest(),
       "profiles_sha1": hashlib.sha1(pathlib.Path("ugv/profiles.py").read_bytes()).hexdigest(),
       "drive_graph_sha1": hashlib.sha1(pathlib.Path("ugv/drive_graph.py").read_bytes()).hexdigest(),
       "approach_sha1": hashlib.sha1(pathlib.Path("ugv/approach.py").read_bytes()).hexdigest(), "pairs": {}}
for src, dst in [("A-ugv1", "B-ugv1"), ("B-ugv1", "A-ugv1"), ("A-fire1", "B-fire1"), ("B-fire1", "A-fire1")]:
    Vs, Vd = fleet(src), fleet(dst)
    body = {"task_id": "AB", "decision_id": "AB", "target_node": node_id_of(Vd.access)}
    ev = asyncio.run(Vs.evaluate(body))
    apd = ev.get("approach") or {}
    row = {"vehicle": Vs.profile.name, "planner": ev["verdict"], "reason": ev.get("detail") or ev.get("reason"), "eta_s": ev.get("eta_sec"),
           "no_directed_route": apd.get("candidates_no_directed_route"), "no_return_path": apd.get("candidates_no_return_path"),
           "approach_mode": apd.get("mode"), "dist_to_target_m": apd.get("dist_to_target_m")}
    if ev["verdict"] == "ACCEPT":
        try:
            asyncio.run(Vs.execute(body))
            pl = Vs.plan
            rc = (pl.detail or {}).get("route_check") or {}
            row.update(route_km=round(pl.route.cum[-1] / 1000, 2) if hasattr(pl.route, "cum") else None,
                       route_roads=len(pl.route.road_ids), route_check_ok=rc.get("ok"),
                       route_check=({k: rc.get(k) for k in ("steering_violations", "body_violations", "worst_excess_m", "label") if k in rc}),
                       route_check_full=rc,              # Codex 1945: mission_items(미션 선형) ok·최악 여유 등 전체 보존
                       junction_relax={k: pl.detail.get(k) for k in ("junction_joins_relaxed", "junction_joins_relaxed_long", "junction_arc_omitted") if pl.detail.get(k)},
                       turn_variants=[[str(x[0])] + [round(v, 2) for v in x[1:]] for x in (getattr(pl.route, "turn_variants", None) or [])])
        except Exception as e:  # noqa: BLE001
            row["execute_error"] = repr(e)[:400]
    res["pairs"][f"{src}->{dst}"] = row
    print(f"{src}->{dst}", json.dumps(row, ensure_ascii=False, default=str)[:700], flush=True)
out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
