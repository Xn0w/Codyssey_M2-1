"""실제 지형 짧은 선별 구간 선정·정적 검사 (Codex 0755 3절, Gazebo 없음). 사용 (ADAIR 루트): python screen_segment.py <tiles_v2> <route_geom.json> <out.json> [min_m]
- 경로 시작(거점 출발)부터 route_pts 누적 거리, 1 km 타일 경계 통과 지점(이음매) 목록.
- 끝점 = 누적 min_m 이상이고 이음매 ≥ 2 개를 지나고 마지막 이음매 뒤 ≥ 150 m (정지 여유) 인 첫 경로 점.
- 구간 정적 검사: 경로 방향 경사 (±5 m 중앙 차분), 횡경사 (진행 직각 ±1.5 m), 속도 상한, 높이 범위 — 특성 기록 (합격 기준 아님; 기존 시험 범위 밖 구간 표시)."""
import json, math, sys
import numpy as np
from PIL import Image
from pathlib import Path
T = Path(sys.argv[1]); G = json.load(open(sys.argv[2], encoding="utf-8")); OUT = Path(sys.argv[3]); MIN_M = float(sys.argv[4]) if len(sys.argv) > 4 else 1500.0
meta = json.load(open(T / "tiles.json", encoding="utf-8")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]; ALT = meta["world_origin_alt_m"]
_img = {}
def z_at(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); name = f"T{i:02d}_{j:02d}"; t = meta["tiles"][name]
    if name not in _img: _img[name] = np.asarray(Image.open(T / name / "heightmap.png"), dtype=np.float64)
    img = _img[name]; x0, y0, x1, y1 = t["bounds"]; n = img.shape[0] - 1
    fc, fr = (x - x0) / (x1 - x0) * n, (y1 - y) / (y1 - y0) * n; c0, r0 = min(int(fc), n - 1), min(int(fr), n - 1); dc, dr = fc - c0, fr - r0
    v = img[r0, c0] * (1 - dc) * (1 - dr) + img[r0, c0 + 1] * dc * (1 - dr) + img[r0 + 1, c0] * (1 - dc) * dr + img[r0 + 1, c0 + 1] * dc * dr
    return name, t["zmin"] + v / 65535.0 * t["span"] - ALT
P = G["route_pts"]; V = G["route_vlim"]
cum = [0.0]
for a, b in zip(P, P[1:]): cum.append(cum[-1] + math.dist(a, b))
seams, end = [], None
for k in range(1, len(P)):
    ta, tb = z_at(*P[k - 1])[0], z_at(*P[k])[0]
    if ta != tb: seams.append({"k": k, "s_m": round(cum[k], 1), "from": ta, "to": tb, "xy": [round(c, 2) for c in P[k]]})
    if cum[k] >= MIN_M and len(seams) >= 2 and cum[k] - seams[-1]["s_m"] >= 150.0: end = k; break
pts, grade, cross = [], [], []
s_grid = np.arange(0.0, cum[end], 5.0)
def at(s):
    k = max(1, int(np.searchsorted(cum, s))); k = min(k, len(P) - 1); a, b = P[k - 1], P[k]; L = cum[k] - cum[k - 1] or 1.0; f = (s - cum[k - 1]) / L
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f), math.atan2(b[1] - a[1], b[0] - a[0]), V[k]
for s in s_grid:
    (x, y), h, vl = at(s); z = z_at(x, y)[1]
    (xa, ya), _, _ = at(max(0.0, s - 5.0)); (xb, yb), _, _ = at(min(cum[end], s + 5.0))
    za, zb = z_at(xa, ya)[1], z_at(xb, yb)[1]; ds = math.dist((xa, ya), (xb, yb)) or 1.0
    nx, ny = -math.sin(h), math.cos(h); zl, zr = z_at(x + 1.5 * nx, y + 1.5 * ny)[1], z_at(x - 1.5 * nx, y - 1.5 * ny)[1]
    g, c = (zb - za) / ds, (zl - zr) / 3.0
    grade.append(g); cross.append(c); pts.append({"s": round(float(s), 1), "xy": [round(x, 2), round(y, 2)], "z": round(z, 3), "grade": round(g, 4), "cross": round(c, 4), "vlim": vl})
ga, ca = np.abs(grade), np.abs(cross)
res = {"route_file": sys.argv[2], "min_m": MIN_M, "end_k": end, "end_s_m": round(cum[end], 1), "end_xy": [round(c, 3) for c in P[end]],
       "start_xy": P[0], "seams_passed": seams, "n_seams": len(seams), "tiles": sorted({z_at(*p)[0] for p in P[:end + 1]}),
       "grade_abs_max": round(float(ga.max()), 4), "grade_abs_p95": round(float(np.percentile(ga, 95)), 4), "grade_min": round(float(min(grade)), 4), "grade_max": round(float(max(grade)), 4),
       "cross_abs_max": round(float(ca.max()), 4), "cross_abs_p95": round(float(np.percentile(ca, 95)), 4),
       "z_range": [round(min(p["z"] for p in pts), 2), round(max(p["z"] for p in pts), 2)], "vlim_max": max(p["vlim"] for p in pts),
       "beyond_tested": {"grade_abs_gt_0.06_m": 5.0 * int((ga > 0.06).sum()), "cross_abs_gt_0.04_m": 5.0 * int((ca > 0.04).sum())},
       "note": "특성 기록 — 시험된 경사 범위(내리막 약 3~6 %) 밖 길이 표시, 합격 기준 아님", "profile": pts}
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ("profile", "seams_passed")}, ensure_ascii=False)); print("seams", [(s["s_m"], s["from"], s["to"]) for s in seams])
