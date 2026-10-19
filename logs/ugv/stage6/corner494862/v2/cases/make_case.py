# -*- coding: utf-8 -*-
"""대표 반경 사례 준비 (시험 도구): 진입 도로 r1 위 출발(교차로 노드 t1 앞 before m, 노드 쪽을 향함) → r2 위 목표.
spawn.txt (Gazebo x,y,z,yaw: z = 타일 표면 − 172.0998 + 0.45 — 494862 출발 자세 46.154 = 표면 45.704 + 0.45 와 같은 규칙), fleet.json (px4), fleet_sim.json, case.json.
사용: python make_case.py <이름> <r1> <t1> <s_start> <r2> <s_target>"""
import json, math, os, sys
from pathlib import Path
A = Path(r"C:\Users\수다쟁이고양이들\Documents\GitHub\ADAIR")
os.environ["UGV_ROAD_SUBSET"] = str(A / "logs/ugv/stage5/tiles_v2c1/road_subset_ab_route_v1.json")
os.environ["ADAIR_TILES_OUT"] = str(A / "logs/ugv/stage5/tiles_v2c1")
sys.path.insert(0, str(A))
from ugv.roads import RoadNetwork
from ugv.geo import FRAME, GZ_FRAME, bearing_deg
from ugv.tools.build_terrain_tiles import Surface, X0, Y0, TILE_M, tile_name
name, r1, t1, s0, r2, st = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5], float(sys.argv[6])
net = RoadNetwork(); S = Surface()
R1 = net.roads[r1]
p = net.at(r1, s0)
d = 1.0 if t1 == R1.b else -1.0
q = net.at(r1, s0 + d * 1.0)
hd = bearing_deg(q.x - p.x, q.y - p.y)
lat, lon = FRAME.to_ll(p.x, p.y)
gx, gy = GZ_FRAME.to_xy(lat, lon)
Z_REF = 172.0998
z = S.z(p.x, p.y) - Z_REF + 0.45
yaw = math.atan2(math.sin(math.radians(90 - hd)), math.cos(math.radians(90 - hd)))
sdf = (A / "logs/ugv/stage5/tiles_v2c1/ab_route_v1.sdf").read_text(encoding="utf-8")
tiles = {tile_name(int((x - X0) // TILE_M), int((y - Y0) // TILE_M)) for x, y in net.polyline(r1, 0, R1.length) + net.polyline(r2, 0, net.roads[r2].length)}
missing = sorted(t for t in tiles if f"model://{t}<" not in sdf)
D = Path(__file__).parent / name
D.mkdir(parents=True, exist_ok=True)
(D / "spawn.txt").write_text(f"1 adair_ugv {gx:.2f},{gy:.2f},{z:.3f},{yaw:.5f} A-ugv1\n", encoding="utf-8")
base = json.loads((A / "logs/ugv/stage6/corner494862/fleet_c.json").read_text(encoding="utf-8"))
base[0]["initial"] = {"lat": lat, "lon": lon, "heading_deg": hd}
(D / "fleet.json").write_text(json.dumps(base, ensure_ascii=False, indent=1), encoding="utf-8")
sim = json.loads((A / "logs/ugv/stage6/corner494862/fleet_c_sim.json").read_text(encoding="utf-8"))
sim[0]["initial"] = {"lat": lat, "lon": lon, "heading_deg": hd}
(D / "fleet_sim.json").write_text(json.dumps(sim, ensure_ascii=False), encoding="utf-8")
case = {"name": name, "r1": r1, "toward": t1, "s_start": s0, "r2": r2, "s_target": st, "target_node": f"RP:{r2}:{st:.1f}",
        "start_frame_xy": [p.x, p.y], "gz_xyz_yaw": [gx, gy, z, yaw], "heading_deg": hd, "surface_z": S.z(p.x, p.y),
        "tiles_touched": sorted(tiles), "tiles_missing_in_world": missing}
(D / "case.json").write_text(json.dumps(case, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(case, ensure_ascii=False))
