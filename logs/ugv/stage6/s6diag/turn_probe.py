import os, sys, json, pathlib, tempfile, math
os.environ["UGV_ROAD_SUBSET"] = sys.argv[1] + "/road_subset_all_included.json"; os.environ.setdefault("UGV_ALLOW_NO_FIRE_DATA", "1")
sys.path.insert(0, ".")
from ugv.roads import RoadNetwork
import ugv.tests.test_multi_vehicle as tm
from ugv.tests.test_multi_vehicle import FLEET_CFG, make_fleet
net = RoadNetwork(); tm.NET = net
cfg = {c["resource_id"]: c for c in FLEET_CFG}
f, _ = make_fleet(pathlib.Path(tempfile.mkdtemp()), [cfg[sys.argv[2]]]); V = f.vehicles[sys.argv[2]]; g = V.graph
for pr, cr in [p.split(">") for p in sys.argv[3:]]:
    a, b = net.roads[pr], net.roads[cr]
    common = {a.a, a.b} & {b.a, b.b}
    print(f"== {pr} -> {cr}  lens {a.length:.1f} / {b.length:.1f}  oneway {a.attrs.get('oneway')} / {b.attrs.get('oneway')}  common node {common}")
    for n in common:
        st = (pr, n)
        ts = g.turns.get(st, [])
        print("   turns from", st, "→", [(t.to, round(t.deflect_deg), t.radius_m and round(t.radius_m, 1), round(t.tangent_m, 1), t.margin_m and round(t.margin_m, 2)) for t in ts])
        other = [r for r in net.roads if n in (net.roads[r].a, net.roads[r].b)]
        print("   roads at node", n, other)
        bt = [x for x in g.blocked_turns if json.dumps(x, default=str).find(cr) >= 0 and json.dumps(x, default=str).find(pr) >= 0]
        print("   blocked_turns mention both:", bt[:3])
        bt2 = [x for x in g.blocked_turns if n in json.dumps(x, default=str)]
        print("   blocked_turns at node:", json.dumps(bt2[:4], ensure_ascii=False, default=str)[:900])
    print("   sample blocked_turn keys:", list(g.blocked_turns[0].keys()) if g.blocked_turns else None, "n_blocked", len(g.blocked_turns))
