"""S6 소방차 A→B (읽기 전용): 계획기와 같은 출발 상태(here_state)로 탐색해 목적지(B-fire1 접근점) 도착 가능성을 단계별로 본다.
실행 (트리에서): python fire_ab_arrival_probe.py <tiles>"""
import os, sys, pathlib, tempfile
os.environ["UGV_ROAD_SUBSET"] = sys.argv[1] + "/road_subset_all_included.json"; os.environ.setdefault("UGV_ALLOW_NO_FIRE_DATA", "1")
sys.path.insert(0, ".")
from ugv.roads import RoadNetwork
import ugv.tests.test_multi_vehicle as tm
from ugv.tests.test_multi_vehicle import FLEET_CFG, make_fleet
net = RoadNetwork(); tm.NET = net
cfg = {c["resource_id"]: c for c in FLEET_CFG}
def fleet(rid):
    f, _ = make_fleet(pathlib.Path(tempfile.mkdtemp()), [cfg[rid]]); return f.vehicles[rid]
Vs, Vd = fleet("A-fire1"), fleet("B-fire1")
g = Vs.graph
start, v0, err = Vs.here_state()
print("start", start, "v0", v0, "err", err)
acc = Vd.access
r = net.roads[acc.road_id]
print("dest access", acc.road_id, round(acc.s, 1), "len", round(r.length, 1), "oneway", r.attrs.get("oneway"))
tree = g.search(start, v0)
for toward, frm_s in ((r.b, 0.0), (r.a, r.length)):
    s = (acc.road_id, toward)
    run = abs(acc.s - frm_s)
    labs = tree["labels"].get(s, [])
    print(f"state {s} allowed={g.allowed(acc.road_id, g.other(acc.road_id, toward))} run_to_access={run:.1f} labels={len(labs)}")
    for T, lab in labs[:6]:
        print("   in from", lab[1], "tan", g.tan.get((lab[1], s)), "tan_min", g.tan_min.get((lab[1], s)), "ok" if g.tan_min.get((lab[1], s), 0) <= run else "ARC_PAST_ACCESS")
    for pin in g.rev.get(s, []):
        t = next(x for x in g.turns[pin] if x.to == s)
        print("   possible entry", pin, "reached" if any(l[1] == pin for _, l in labs) else ("pin_reached" if pin in tree["dist"] else "pin_NOT_reached"),
              "T", t.tangent_m, "Tmin", round(t.tangent_min, 2), "R", t.radius_m, "alts", [(round(a[0], 1), round(a[1], 1)) for a in t.alts])
arr = g.arrivals(tree, acc)
print("arrivals", arr)
