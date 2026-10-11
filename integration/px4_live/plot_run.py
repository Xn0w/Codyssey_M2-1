"""통합 실행 기록 → 계획·실제 궤적 비교 그림 (SVG). 지역 평면 좌표 (ugv.geo.FRAME), Gazebo 궤적은 GZ 좌표 → 위경도 → 지역 평면.
  python integration/px4_live/plot_run.py logs/integ/run_<시각>
UAV 계획 = 거점 → 목표 직선 (UAV 에이전트 경로: 고도 맞춤 → 수평 직선 이동). UGV 계획 = 같은 코드·설정(구역 도로망·횡가속)으로 다시 계산한
화재 접근 경로 (실행 때 보낸 미션 원본이 아니다 — 그림에 표시)."""
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main(run: Path):
    prof = json.loads((run / "profile.json").read_text(encoding="utf-8"))
    os.environ["UGV_ROAD_SUBSET"] = str(ROOT / prof["ugv"]["UGV_ROAD_SUBSET"])
    os.environ["UGV_LAT_ACCEL"] = prof["ugv"].get("UGV_LAT_ACCEL", "1.5")
    import gz_bridge as gb
    from ugv.geo import FRAME, GZ_FRAME
    from ugv.roads import RoadNetwork
    from ugv.tools.drive_test import load_track
    net = RoadNetwork()
    col, row = (int(v) for v in prof["env"]["ENV_IGNITION"].split(","))
    fla, flo = gb.grid_cell_to_latlon(col, row)
    fx, fy = FRAME.to_xy(fla, flo)
    hx, hy = FRAME.to_xy(38.0613774, 128.1684755)

    def track(name):
        p = run / f"track_{name}.csv"
        if not p.exists():
            return []
        out = []
        for r in load_track(p)[::10]:
            out.append(FRAME.to_xy(*GZ_FRAME.to_ll(r["x"], r["y"])))
        return out
    uav, ugv = track("x500_0"), track("adair_ugv_1")
    # UGV 계획 (다시 계산)
    plan = []
    try:
        import asyncio
        import tempfile
        from interfaces.exec_store import ExecStore
        from ugv.clock import ManualClock
        from ugv.fire import StaticFireSource
        from ugv.server import Fleet
        fl = json.loads((ROOT / prof["ugv"]["UGV_VEHICLES_JSON"]).read_text(encoding="utf-8"))
        sx, sy, syaw = (float(v) for v in prof["spawn"][1].split()[2].split(",")[:2] + [prof["spawn"][1].split()[2].split(",")[3]])
        la0, lo0 = GZ_FRAME.to_ll(sx, sy)
        f = Fleet([{**fl[0], "driver": "sim", "initial": {"lat": la0, "lon": lo0, "heading_deg": 90 - math.degrees(syaw)}}], net=net,
                  fire_source=StaticFireSource([{"cell_id": f"{col}_{row}", "lat": fla, "lon": flo, "fire_state": "BURNING",
                                                 "cell_size_m": 90}], "PLOT"),
                  clock=ManualClock(), store=ExecStore(Path(tempfile.mkdtemp()) / "t.json"))
        A = f.vehicles[fl[0]["resource_id"]]
        st, v0, _ = A.here_state()
        pl = A._approach({"task_id": "P", "target": {"lat": fla, "lon": flo}}, st, v0)
        plan = pl.route.pts if pl.route else []
    except Exception as e:  # noqa: BLE001
        print("UGV 계획 재계산 실패:", e)
    pts = uav + ugv + plan + [(fx, fy), (hx, hy)]
    x0, x1 = min(p[0] for p in pts) - 150, max(p[0] for p in pts) + 150
    y0, y1 = min(p[1] for p in pts) - 150, max(p[1] for p in pts) + 150
    W = 900
    s = W / (x1 - x0)
    H = int((y1 - y0) * s)
    X = lambda x: (x - x0) * s
    Y = lambda y: (y1 - y) * s
    poly = lambda P, c, w, extra="": (f'<polyline points="{" ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in P)}" fill="none" '
                                      f'stroke="{c}" stroke-width="{w}" {extra}/>') if len(P) > 1 else ""
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H + 60}"><rect width="100%" height="100%" fill="white"/>']
    for r in net.roads.values():
        if any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in r.xy):
            parts.append(poly(r.xy, "#ccc", 2))
    half = 45 * s
    parts.append(f'<rect x="{X(fx) - half:.1f}" y="{Y(fy) - half:.1f}" width="{2 * half:.1f}" height="{2 * half:.1f}" fill="#f88" opacity="0.6"/>')
    parts.append(f'<circle cx="{X(fx):.1f}" cy="{Y(fy):.1f}" r="{(45 + 100) * s:.1f}" fill="none" stroke="#f55" stroke-dasharray="4 3"/>')
    parts.append(poly([(hx, hy), (fx, fy)], "#88f", 1.5, 'stroke-dasharray="6 4"'))
    parts.append(poly(plan, "#2a2", 2, 'stroke-dasharray="6 4"'))
    parts.append(poly(uav, "#00c", 2))
    parts.append(poly(ugv, "#060", 3))
    parts.append(f'<circle cx="{X(hx):.1f}" cy="{Y(hy):.1f}" r="6" fill="black"/>')
    leg = [("#00c", "UAV 실제 (Gazebo)"), ("#88f", "UAV 계획 (거점→목표 직선)"), ("#060", "UGV 실제 (Gazebo)"),
           ("#2a2", "UGV 계획 (같은 코드로 다시 계산)"), ("#f88", f"화재 칸 {col}_{row}"), ("#f55", "칸 경계 +100 m")]
    for k, (c, t) in enumerate(leg):
        parts.append(f'<rect x="{10 + 300 * (k % 3)}" y="{H + 12 + 22 * (k // 3)}" width="14" height="10" fill="{c}"/>'
                     f'<text x="{28 + 300 * (k % 3)}" y="{H + 21 + 22 * (k // 3)}" font-size="12" font-family="sans-serif">{t}</text>')
    parts.append("</svg>")
    out = run / "trajectory.svg"
    out.write_text("\n".join(parts), encoding="utf-8")
    print("그림:", out)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
