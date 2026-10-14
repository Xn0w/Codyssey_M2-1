"""S6 오프라인 (읽기 전용): 지정 회전들에 대해 turn_fit 과 같은 검사를 모든 R_STEPS 반경 후보로 돌려 표로 출력 (Codex 1626 최소 검증 1단계).
실행 (통합 트리에서): python radius_table.py <tiles> <rid> <rin>:<node>:<rout> ...   — 각 후보: R, 접선 T, 원호 통과, 방향선 포함 여유 m, 추종 여유 충족."""
import os, sys, json, math, pathlib, tempfile
os.environ["UGV_ROAD_SUBSET"] = sys.argv[1] + "/road_subset_all_included.json"; os.environ.setdefault("UGV_ALLOW_NO_FIRE_DATA", "1")
sys.path.insert(0, ".")
from ugv.roads import RoadNetwork
import ugv.drive_graph as DG
import ugv.tests.test_multi_vehicle as tm
from ugv.tests.test_multi_vehicle import FLEET_CFG, make_fleet
net = RoadNetwork(); tm.NET = net
cfg = {c["resource_id"]: c for c in FLEET_CFG}
f, _ = make_fleet(pathlib.Path(tempfile.mkdtemp()), [cfg[sys.argv[2]]]); g = f.vehicles[sys.argv[2]].graph
out = {}
for spec in sys.argv[3:]:
    rin, n, rout = spec.split(":")
    u, w = g._dir(rin, n, out=False), g._dir(rout, n, out=True)
    strips = g._strips(n)
    Lin, Lout = net.roads[rin].length, net.roads[rout].length
    D = math.atan2(u[0] * w[1] - u[1] * w[0], u[0] * w[0] + u[1] * w[1]); ad = abs(D); sg = 1 if D > 0 else -1
    hu, hw = math.atan2(u[1], u[0]), math.atan2(w[1], w[0])
    rows = []
    for fct in reversed(DG.R_STEPS):
        R = g.p.r_min * fct; T = R * math.tan(ad / 2)
        geo = not (T > min(Lin, DG.STRIP_LEN_M, DG.TURN_TANGENT_MAX_M) + 1 or T > min(Lout, DG.STRIP_LEN_M, DG.TURN_TANGENT_MAX_M) + 1)
        m_arc = m = None
        if geo:
            P1 = (-T * u[0], -T * u[1]); C = (P1[0] - u[1] * sg * R, P1[1] + u[0] * sg * R)
            floor = -DG.CHECK_TOL_M; m = math.inf; k_n = max(12, math.ceil(math.degrees(ad) / DG.TURN_FIT_STEP_DEG))
            for k in range(k_n + 1):
                hd = hu + sg * ad * k / k_n; ch, sh = math.cos(hd), math.sin(hd)
                m = min(m, g._pose_clear(C[0] + R * sh * sg, C[1] - R * ch * sg, hd, strips, floor))
            m_arc = m
            if m >= floor:
                dl_in, dl_out = min(DG.DIR_LEN_M, Lin), min(DG.DIR_LEN_M, Lout)
                dd = T + 1.0
                while dd <= dl_in:
                    m = min(m, g._pose_clear(-dd * u[0], -dd * u[1], hu, strips, -1.0)); dd += 1.0
                dd = T + 1.0
                while dd <= dl_out:
                    m = min(m, g._pose_clear(dd * w[0], dd * w[1], hw, strips, -1.0)); dd += 1.0
        rows.append({"R": round(R, 2), "T": round(T, 2), "tangent_fits": geo, "arc_margin": None if m_arc is None else round(m_arc, 3),
                     "arc_pass": m_arc is not None and m_arc >= -DG.CHECK_TOL_M, "margin_with_dirlines": None if m is None else round(m, 3),
                     "meets_track_margin": m is not None and m_arc >= -DG.CHECK_TOL_M and m >= g.p.track_margin_m,
                     "v_turn": round(min(g.road_speed(net.roads[rin]), g.road_speed(net.roads[rout]), math.sqrt(g.p.lat_accel_mps2 * R)), 2)})
    chosen = [t for t in g.turns.get((rin, n), []) if t.to[0] == rout]
    out[spec] = {"deflect_deg": round(math.degrees(ad), 1), "Lin": round(Lin, 1), "Lout": round(Lout, 1), "track_margin_need": g.p.track_margin_m,
                 "chosen": [(t.radius_m, t.tangent_m, t.margin_m) for t in chosen], "candidates": rows}
    print(f"== {spec} deflect {math.degrees(ad):.1f}° Lin {Lin:.1f} Lout {Lout:.1f} need {g.p.track_margin_m} chosen {out[spec]['chosen']}")
    for r in rows:
        if r["tangent_fits"]:
            print(f"   R {r['R']:7.2f} T {r['T']:6.2f} arc {r['arc_margin']} pass {r['arc_pass']} m {r['margin_with_dirlines']} ok {r['meets_track_margin']} v {r['v_turn']}")
pathlib.Path(sys.argv[2] + "_radius_table.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
