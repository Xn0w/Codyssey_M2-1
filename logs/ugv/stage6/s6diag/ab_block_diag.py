"""S6 정적 진단 (읽기 전용): ab_connect 가 REJECT(no_directed_route) 한 A↔B 쌍에서 지도상 최단 경로를 따라
방향 그래프(진행 방향·회전 가능)로 처음 도달 못 하는 도로와 그 직전 전이를 찾고, DriveGraph.blocked_turns·sharp_roads 와 대조.
실행 (ADAIR_wt_integ 에서): python ../ADAIR/logs/ugv/stage6/s6diag/ab_block_diag.py <tiles> <out.json>   — road_subset 파일을 쓰지 않는다."""
import heapq, json, os, pathlib, sys, tempfile
tiles = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2])
os.environ["UGV_ROAD_SUBSET"] = str(tiles / "road_subset_all_included.json")
os.environ.setdefault("UGV_ALLOW_NO_FIRE_DATA", "1")
sys.path.insert(0, ".")
from ugv.roads import RoadNetwork
import ugv.tests.test_multi_vehicle as tm
from ugv.tests.test_multi_vehicle import FLEET_CFG, make_fleet
from ugv.drive_graph import DirPos
net = RoadNetwork(); tm.NET = net
cfg = {c["resource_id"]: c for c in FLEET_CFG}
def fleet(rid):
    f, _ = make_fleet(pathlib.Path(tempfile.mkdtemp()), [cfg[rid]]); return f.vehicles[rid]
G = {}
for rid, r in net.roads.items():
    ow = r.attrs.get("oneway")
    if ow in (None, "BOTH", "A_TO_B"): G.setdefault(r.a, []).append((r.b, rid, r.length))
    if ow in (None, "BOTH", "B_TO_A"): G.setdefault(r.b, []).append((r.a, rid, r.length))
def shortest(src, dst):
    best = None
    for s0 in (net.roads[src].a, net.roads[src].b):
        dist, prev, pq = {s0: 0.0}, {}, [(0.0, s0)]
        while pq:
            d, u = heapq.heappop(pq)
            if d != dist[u]: continue
            for v, rid, L in G.get(u, []):
                if v not in dist or d + L < dist[v]:
                    dist[v], prev[v] = d + L, (u, rid); heapq.heappush(pq, (d + L, v))
        for t in (net.roads[dst].a, net.roads[dst].b):
            if t in dist and (best is None or dist[t] < best[0]):
                path, u = [], t
                while u != s0:
                    u, r_ = prev[u]; path.append((r_, u))
                best = (dist[t], path[::-1])
    return best
res = {}
for src, dst in [("A-ugv1", "B-ugv1"), ("B-ugv1", "A-ugv1"), ("A-fire1", "B-fire1"), ("B-fire1", "A-fire1")]:
    Vs, Vd = fleet(src), fleet(dst)
    g = Vs.graph
    sp = shortest(Vs.access.road_id, Vd.access.road_id)
    reached = set()
    for tw in (net.roads[Vs.access.road_id].a, net.roads[Vs.access.road_id].b):
        tree = g.search(DirPos(Vs.access, tw), 0.0)
        reached |= {s[0] for s in tree["dist"]}
    path_roads = [r for r, _ in sp[1]]
    first = next((k for k, r in enumerate(path_roads) if r not in reached and r != Vs.access.road_id), None)
    row = {"vehicle": Vs.profile.name, "src_road": Vs.access.road_id, "dst_road": Vd.access.road_id, "map_km": round(sp[0] / 1000, 1),
           "path_roads": len(path_roads), "reached_states_roads": len(reached), "dst_reached": Vd.access.road_id in reached}
    if first is not None:
        prev_r, cur_r = path_roads[first - 1] if first > 0 else Vs.access.road_id, path_roads[first]
        node = sp[1][first - 1][1] if first > 0 else None
        bt = [b for b in g.blocked_turns if (str(b.get("from", "")).find(prev_r) >= 0 or prev_r in json.dumps(b)) and cur_r in json.dumps(b)]
        row["first_unreached"] = {"index": first, "prev_road": prev_r, "road": cur_r, "prev_reached": prev_r in reached,
                                  "road_sharp": cur_r in g.sharp_roads, "prev_sharp": prev_r in g.sharp_roads,
                                  "blocked_turns_matching": bt[:4],
                                  "road_attrs": {k: net.roads[cur_r].attrs.get(k) for k in ("oneway", "lanes", "highway", "name")}}
    res[f"{src}->{dst}"] = row
    print(f"{src}->{dst}", json.dumps(row, ensure_ascii=False, default=str)[:900], flush=True)
out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
