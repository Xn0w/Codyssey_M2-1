# -*- coding: utf-8 -*-
"""120개 경로 4조건 오프라인 비교 (시험 도구). 원 탐색 스크립트(scratchpad sweep2.py: 거점 A·B 각 60 개, random.seed(1), 길이 ≥ 200 m)와
같은 방식으로 경로 목록을 한 번 만들어 저장하고(list), 조건별 소스 트리에서 같은 목록을 다시 계획해 비교한다(eval).
  python sweep120.py list <소스 트리> <routes.json>
  python sweep120.py eval <소스 트리> <routes.json> <lat> <out.json>
ETA 두 가지: eta_plan = 연속 계획 속도(plan_speeds.eta_s), eta_items = PX4 항목 속도로 지점 사이 직선 거리를 나눈 단순 추정 (가감속 무시).
원호 계획 초과 = 판정기 v2 와 같은 독립 원 검출(detect_arcs, 생성 정보 안 씀)로 찾은 확인 원호(R ≤ 60 m) 위 계획 최고 − √(a·R)."""
import json, math, random, sys, hashlib
mode, tree = sys.argv[1], sys.argv[2]
sys.path.insert(0, tree)
import ugv
assert ugv.__file__.replace("\\", "/").lower().startswith(tree.replace("\\", "/").lower()), ugv.__file__
from ugv.roads import RoadNetwork, plan_speeds
from ugv.drive_graph import access_point
NET = RoadNetwork(); G = NET.graph


def routes_list(n_per=60, seed=1):
    random.seed(seed)
    out = []
    for base in ("A", "B"):
        acc = access_point(NET, base)
        st = G.dirpos(acc[0], acc[1]); tree_ = G.search(st, 0.0)
        rids = [r for r in NET.roads if (r, NET.roads[r].b) in tree_["dist"] or (r, NET.roads[r].a) in tree_["dist"]]
        random.shuffle(rids); n = 0
        for rid in rids:
            if n >= n_per:
                break
            r = NET.roads[rid]
            u = random.uniform(0.2, 0.8)
            p = NET.at(rid, r.length * u)
            try:
                arrs = G.arrivals(tree_, p)
                if not arrs:
                    continue
                route = G.build_route(tree_, p, min(arrs, key=lambda a: a.time_s))
            except Exception:
                continue
            if route.length < 200:
                continue
            out.append({"base": base, "rid": rid, "s": r.length * u, "len": route.length,
                        "pts_sha": hashlib.sha256(json.dumps([[round(x, 4), round(y, 4)] for x, y in route.pts]).encode()).hexdigest()[:16]})
            n += 1
    return out


def build(rec, cache={}):
    if rec["base"] not in cache:
        acc = access_point(NET, rec["base"])
        cache[rec["base"]] = G.search(G.dirpos(acc[0], acc[1]), 0.0)
    tree_ = cache[rec["base"]]
    p = NET.at(rec["rid"], rec["s"])
    arrs = G.arrivals(tree_, p)
    return G.build_route(tree_, p, min(arrs, key=lambda a: a.time_s))


if mode == "list":
    L = routes_list()
    open(sys.argv[3], "w", encoding="utf-8").write(json.dumps(L, indent=0))
    print(len(L))
    sys.exit()

sys.path.insert(0, r"C:\Users\수다쟁이고양이들\Documents\GitHub\ADAIR\logs\ugv\stage6\corner494862")
import judge_corner_v2 as J
L = json.load(open(sys.argv[3], encoding="utf-8")); lat = float(sys.argv[4])
rows = []
for rec in L:
    route = build(rec)
    sha = hashlib.sha256(json.dumps([[round(x, 4), round(y, 4)] for x, y in route.pts]).encode()).hexdigest()[:16]
    sp = plan_speeds(route, profile=G.p, lat_accel=lat)
    on = sp.items_on_path or sp.items
    t, prev = 0.0, sp.pts[0]
    for x, y, v in on:
        t += math.dist(prev, (x, y)) / max(v, 1.0); prev = (x, y)
    arcs = [a for a in J.detect_arcs(sp.pts, sp.cum) if a["status"] == "CONFIRMED" and a["R"] <= 60.0]
    # 항목 인덱스 (계획선 위)
    pos = {(round(x, 6), round(y, 6)): k for k, (x, y) in enumerate(sp.pts)}
    idx = [pos.get((round(x, 6), round(y, 6))) for x, y, _ in on]
    ov = []
    for a in arcs:
        vc = math.sqrt(lat * a["R"])
        pmax = max(sp.v[k] for k in range(a["i0"], a["i1"] + 1))
        imax = None
        for n in range(len(idx)):
            if idx[n] is None:
                continue
            lo = sp.cum[idx[n - 1]] - 3.0 if n > 0 and idx[n - 1] is not None else 0.0
            if lo <= a["s1"] and sp.cum[idx[n]] >= a["s0"]:
                imax = max(imax or 0.0, on[n][2])
        ov.append({"R": round(a["R"], 3), "deg": round(a["deg"], 1), "len": round(a["s1"] - a["s0"], 2),
                   "plan_over": round(pmax - vc, 4), "item_over": None if imax is None else round(imax - vc, 4)})
    rows.append({"base": rec["base"], "rid": rec["rid"], "len": round(route.length, 1), "pts_same": sha == rec["pts_sha"],
                 "eta_plan": round(sp.eta_s, 3), "eta_items": round(t, 3), "n_items": len(on),
                 "min_item_v": min(v for _, _, v in on), "n_gen_arcs": len(getattr(route, "arcs", []) or []), "arcs": ov})
json.dump({"tree": tree, "lat": lat, "rows": rows}, open(sys.argv[5], "w", encoding="utf-8"), ensure_ascii=False)
print(len(rows), sum(r["pts_same"] for r in rows))
