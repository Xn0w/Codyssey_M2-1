"""ab_route_v1 사전 검사 (Codex 0155 5절 2): 네 경로 도로 ID ⊂ 월드 부분집합, 경로·미션 점이 타일 합집합 경계에서 ≥ 25 m 안쪽,
경로에 제외 도로(교량·터널 추정·자동차전용) 없음. 사용: python check_ab_world.py <tiles_v2> <out.json>"""
import glob, json, math, sys
from pathlib import Path
T = Path(sys.argv[1]); out = {}
meta = json.load(open(T / "tiles.json", encoding="utf-8")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]
sub = json.load(open(T / "road_subset_ab_route_v1.json", encoding="utf-8"))
roads, tiles = set(sub["roads"]), set(sub["tiles"])
excl = meta.get("roads_excluded") or {}
excl_ids = set()
for k, v in excl.items():
    if isinstance(v, list): excl_ids |= set(map(str, v))
    elif isinstance(v, dict): excl_ids |= set(map(str, v.keys()))
def in_tiles(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); return f"T{i:02d}_{j:02d}" in tiles
def margin_ok(x, y, m=25.0):
    return all(in_tiles(x + dx, y + dy) for dx, dy in ((0, 0), (m, 0), (-m, 0), (0, m), (0, -m), (m, m), (m, -m), (-m, m), (-m, -m)))
for f in sorted(glob.glob("route_geom_*.json")):
    g = json.load(open(f, encoding="utf-8")); k = f[len("route_geom_"):-5]
    rid = set(map(str, g["road_ids"]))
    miss = sorted(rid - roads); ex = sorted(rid & excl_ids)
    bad_pts = [p for p in g["route_pts"] if not margin_ok(*p)]
    bad_items = [p[:2] for p in g["mission_items"] if not margin_ok(*p[:2])]
    out[k] = {"roads": len(rid), "roads_missing_from_world_subset": miss, "excluded_roads_on_route": ex,
              "route_pts_outside_25m": len(bad_pts), "mission_items_outside_25m": len(bad_items), "examples": bad_pts[:3]}
    print(k, "roads", len(rid), "missing", len(miss), "excluded", len(ex), "pts_out", len(bad_pts), "items_out", len(bad_items))
out["excluded_categories"] = {k: (len(v) if hasattr(v, "__len__") else v) for k, v in excl.items()}
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
