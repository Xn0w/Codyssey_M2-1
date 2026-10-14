"""단계 B 구간의 서버 계획 오프라인 확인 (Codex 0814 2절 B, Gazebo 없음). 서버 트리 (ADAIR_wt_hook 03d5b5d) 에서:
python plan_check_b.py <tiles_v2> <seg_json> <idx> <out.json>
- 월드 부분집합 road_subset_ab_route_v1.json, UGV_MAX_SPEED_KMH=20 (선별 임시 프로필) 로 make_fleet → A-ugv1 을 구간 시작 (위치·진행 방향) 에 두고
  구간 끝 좌표로 evaluate/execute → 계획 경로·미션 항목·속도 상한·도로 ID. 기대 구간 (B→A 경로 s0~s1) 과 계획 선형 최대 이격, 계획 길이, 최고 계획 속도 기록."""
import asyncio, hashlib, json, math, os, pathlib, sys, tempfile
tiles = pathlib.Path(sys.argv[1]); seg = json.load(open(sys.argv[2], encoding="utf-8"))["top"][int(sys.argv[3])]; out = pathlib.Path(sys.argv[4])
os.environ["UGV_ROAD_SUBSET"] = str(tiles / "road_subset_ab_route_v1.json"); os.environ.setdefault("UGV_ALLOW_NO_FIRE_DATA", "1")
os.environ["UGV_MAX_SPEED_KMH"] = "20"
for k in ("UGV_STOP_CAP_FIRST", "UGV_STOP_ITEMS_RAMP", "UGV_PX4_END_EXTEND"): os.environ[k] = "1"
sys.path.insert(0, ".")
from ugv import config  # noqa: E402
from ugv.geo import GZ_FRAME  # noqa: E402
from ugv.roads import RoadNetwork  # noqa: E402
import ugv.tests.test_multi_vehicle as tm  # noqa: E402
from ugv.tests.test_multi_vehicle import FLEET_CFG, make_fleet  # noqa: E402
net = RoadNetwork(); tm.NET = net
cfg = json.loads(json.dumps({c["resource_id"]: c for c in FLEET_CFG}["A-ugv1"]))
sx, sy = seg["start_xy"]; lat, lon = GZ_FRAME.to_ll(sx, sy); hd = (90.0 - math.degrees(seg["start_heading_rad_enu"])) % 360.0
cfg["initial"] = {"lat": lat, "lon": lon, "heading_deg": hd}
f, _ = make_fleet(pathlib.Path(tempfile.mkdtemp()), [cfg]); V = f.vehicles["A-ugv1"]
ex, ey = seg["end_xy"]; elat, elon = GZ_FRAME.to_ll(ex, ey)
body = {"task_id": "SB", "decision_id": "SB", "target": {"lat": elat, "lon": elon}}
ev = asyncio.run(V.evaluate(body)); row = {"verdict": ev["verdict"], "eta_s": ev.get("eta_sec"), "reasons": ev.get("reasons") or ev.get("reason"),
                                            "max_speed_mps_config": round(config.MAX_SPEED_MPS, 3), "profile_max_speed_mps": round(V.profile.max_speed_mps, 3)}
if ev["verdict"] == "ACCEPT":
    body["target_node"] = (ev.get("target_node") or {}).get("node_id")
    asyncio.run(V.execute(body)); pts = [tuple(p) for p in V.plan.route.pts]
    G = json.load(open(pathlib.Path(sys.argv[2]).parent / seg["route"], encoding="utf-8"))["route_pts"]
    def dseg(q, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]; L = dx * dx + dy * dy or 1e-9; t = max(0.0, min(1.0, ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / L))
        return math.dist(q, (a[0] + t * dx, a[1] + t * dy))
    def dmin(q): return min(dseg(q, G[i], G[i + 1]) for i in range(len(G) - 1))   # 점-선분 거리 (첫 판의 점-꼭짓점 20.6 m 는 측정 결함)
    dev = max(dmin(p) for p in pts)
    row.update(route_m=round(sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)), 1), road_ids=list(V.plan.route.road_ids),
               vlim_max_mps=round(max(V.plan.route.vlim), 3), start_xy=[round(c, 2) for c in pts[0]], end_xy=[round(c, 2) for c in pts[-1]],
               max_dev_from_expected_route_m=round(dev, 2), n_pts=len(pts),
               mission_items=[[round(x, 2), round(y, 2), round(v, 2)] for (x, y, v) in (getattr(getattr(V, "speed", None), "items", None) or [])][:60],
               dest={"road_id": V.plan.dest.road_id, "s": round(V.plan.dest.s, 2), "xy": [round(V.plan.dest.x, 2), round(V.plan.dest.y, 2)]})
row.update(seg=seg, start_ll=[lat, lon], start_heading_deg=round(hd, 3), end_ll=[elat, elon], git_head=os.popen("git rev-parse --short HEAD").read().strip(),
           git_dirty_ugv=os.popen("git status --porcelain --untracked-files=no -- ugv").read().strip(), subset_sha1=hashlib.sha1((tiles / "road_subset_ab_route_v1.json").read_bytes()).hexdigest())
json.dump(row, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in row.items() if k not in ("mission_items", "seg")}, ensure_ascii=False))
