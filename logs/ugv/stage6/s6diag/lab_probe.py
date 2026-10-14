import os, sys, json, pathlib, tempfile, inspect
os.environ["UGV_ROAD_SUBSET"] = sys.argv[1] + "/road_subset_all_included.json"; os.environ.setdefault("UGV_ALLOW_NO_FIRE_DATA", "1")
sys.path.insert(0, ".")
from ugv.roads import RoadNetwork
import ugv.tests.test_multi_vehicle as tm
from ugv.tests.test_multi_vehicle import FLEET_CFG, make_fleet
from ugv.drive_graph import DirPos
net = RoadNetwork(); tm.NET = net
cfg = {c["resource_id"]: c for c in FLEET_CFG}
f, _ = make_fleet(pathlib.Path(tempfile.mkdtemp()), [cfg[sys.argv[2]]]); V = f.vehicles[sys.argv[2]]; g = V.graph
prev_r, road = sys.argv[3], sys.argv[4]
for tw in (net.roads[V.access.road_id].a, net.roads[V.access.road_id].b):
    tree = g.search(DirPos(V.access, tw), 0.0)
    labs = tree["labels"]
    for st, lst in labs.items():
        if st[0] in (prev_r, road):
            print("start toward", tw, "state", st, "labels", [(round(T, 1), lab[1]) for T, lab in lst][:4])
    for st in [s for s in labs if s[0] == road]:
        r = net.roads[road]
        for T, lab in labs[st]:
            tin = g.tan.get((lab[1], st), 0.0)
            for t in g.turns.get(st, ()):
                print(f"   in from {lab[1]} tin={tin:.1f}  out→{t.to} tout={t.tangent_m:.1f} len={r.length:.1f} lab_ok={g._lab_ok(tin, t.tangent_m, r.length)}")
print("---- prev road check")
st = (prev_r, [s for s in g.turns if s[0] == prev_r and any(t.to[0] == road for t in g.turns[s])][0][1])
r = net.roads[prev_r]
for pin in [p for (p, s) in g.tan if s == st]:
    tin = g.tan[(pin, st)]
    for t in g.turns[st]:
        print(f"on {prev_r} (len {r.length:.1f}) in from {pin} tin={tin:.1f} → {t.to} tout={t.tangent_m:.1f} sum={tin + t.tangent_m:.1f} lab_ok={g._lab_ok(tin, t.tangent_m, r.length)} radius={t.radius_m} deflect={t.deflect_deg:.0f}")
