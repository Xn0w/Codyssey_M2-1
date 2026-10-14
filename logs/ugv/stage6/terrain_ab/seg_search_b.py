"""단계 B 구간 탐색 (Codex 0814 2절 B, Gazebo 없음, WSL python3): UGV 두 경로 (A→B, B→A) 위에서
길이 200~400 m, 타일 이음매 ≥ 1, 구간 + 앞 20 m (스폰 여유) + 뒤 40 m (정지·연장 여유) 전체 |종단경사| ≤ 3 % 인 창.
경사 = 5 m 간격 ±5 m 중앙 차분, 횡경사 = 진행 직각 ±1.5 m. 이음매는 구간 안쪽 (시작 ≥ 50 m 뒤, 끝 ≥ 80 m 앞). 출력: 후보 상위 (최대 경사 작은 순)."""
import json, math, sys
import numpy as np
from PIL import Image
from pathlib import Path
T = Path(sys.argv[1]); OUT = Path(sys.argv[2]); routes = sys.argv[3:]
meta = json.load(open(T / "tiles.json", encoding="utf-8")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]; ALT = meta["world_origin_alt_m"]; _img = {}
def z_at(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); name = f"T{i:02d}_{j:02d}"; t = meta["tiles"][name]
    if name not in _img: _img[name] = np.asarray(Image.open(T / name / "heightmap.png"), dtype=np.float64)
    img = _img[name]; x0, y0, x1, y1 = t["bounds"]; n = img.shape[0] - 1
    fc, fr = (x - x0) / (x1 - x0) * n, (y1 - y) / (y1 - y0) * n; c0, r0 = min(int(fc), n - 1), min(int(fr), n - 1); dc, dr = fc - c0, fr - r0
    v = img[r0, c0] * (1 - dc) * (1 - dr) + img[r0, c0 + 1] * dc * (1 - dr) + img[r0 + 1, c0] * (1 - dc) * dr + img[r0 + 1, c0 + 1] * dc * dr
    return name, t["zmin"] + v / 65535.0 * t["span"] - ALT
cands = []
for rf in routes:
    G = json.load(open(rf, encoding="utf-8")); P = G["route_pts"]; V = G["route_vlim"]
    cum = np.concatenate([[0.0], np.cumsum([math.dist(a, b) for a, b in zip(P, P[1:])])])
    def at(s):
        k = int(min(max(1, np.searchsorted(cum, s)), len(P) - 1)); a, b = P[k - 1], P[k]; L = cum[k] - cum[k - 1] or 1.0; f = (s - cum[k - 1]) / L
        return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f), math.atan2(b[1] - a[1], b[0] - a[0]), V[k]
    S = np.arange(5.0, cum[-1] - 5.0, 5.0); tile, grade, cross, xy, hd = [], [], [], [], []
    for s in S:
        (x, y), h, _ = at(s); (xa, ya), _, _ = at(s - 5); (xb, yb), _, _ = at(s + 5)
        tile.append(z_at(x, y)[0]); ds = math.dist((xa, ya), (xb, yb)) or 1.0; grade.append((z_at(xb, yb)[1] - z_at(xa, ya)[1]) / ds)
        nx, ny = -math.sin(h), math.cos(h); cross.append((z_at(x + 1.5 * nx, y + 1.5 * ny)[1] - z_at(x - 1.5 * nx, y - 1.5 * ny)[1]) / 3.0); xy.append((x, y)); hd.append(h)
    grade = np.abs(grade); cross = np.abs(cross); n = len(S)
    seam_idx = [i for i in range(1, n) if tile[i] != tile[i - 1]]
    for si in seam_idx:
        for L in (300.0, 250.0, 350.0, 200.0, 400.0):
            for pre in range(10, int((L - 80) / 5)):          # 이음매가 시작 뒤 ≥ 50 m, 끝 앞 ≥ 80 m
                i0 = si - pre; i1 = i0 + int(L / 5)
                if i0 - 4 < 0 or i1 + 8 >= n or (si - i0) * 5 < 50 or (i1 - si) * 5 < 80: continue
                g = grade[i0 - 4:i1 + 9]; c = cross[i0 - 4:i1 + 9]
                if g.max() <= 0.03:
                    cands.append({"route": Path(rf).name, "s0": float(S[i0]), "s1": float(S[i1]), "len_m": L, "seam_s": float(S[si]), "seam": [tile[si - 1], tile[si]],
                                  "grade_abs_max": round(float(g.max()), 4), "grade_abs_p95": round(float(np.percentile(g, 95)), 4), "cross_abs_max": round(float(c.max()), 4),
                                  "start_xy": [round(v, 3) for v in xy[i0]], "start_heading_rad_enu": round(hd[i0], 4), "end_xy": [round(v, 3) for v in xy[i1]],
                                  "start_ground_z": round(z_at(*xy[i0])[1], 3), "vlim_kmh_max": round(max(V[int(np.searchsorted(cum, s))] for s in S[i0:i1 + 1]) * 3.6, 1)})
                    break
cands.sort(key=lambda c: (c["grade_abs_max"], c["cross_abs_max"]))
json.dump({"n": len(cands), "rule": "200~400 m, 이음매 ≥ 1 (시작 뒤 ≥ 50 m, 끝 앞 ≥ 80 m), 앞 20 m·뒤 40 m 포함 |경사| ≤ 3 %", "top": cands[:30]}, open(OUT, "w"), ensure_ascii=False, indent=1)
print(len(cands)); [print(json.dumps(c, ensure_ascii=False)) for c in cands[:8]]
