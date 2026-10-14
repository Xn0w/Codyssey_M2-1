"""B 단계 4 타일 모서리·Y 경계 구간 탐색 (Codex 0940 2절 B, WSL python3, Gazebo 없음).
ab_route_v1 160 타일 중 네 타일이 모두 있는 모서리 (x = OX + i·1000, y = OY + j·1000) 마다:
 - 모서리 정지용: 모서리 중심 ±6 m 정사각형의 최대 경사 (1 m 격자 중앙 차분) — 차량 (4.2×1.8, 회전 반경 고려) 이 들어갈 여유.
 - Y 경계 통과용: 모서리에서 x 로 +40 m 떨어진 남북 직선 (y = 경계 ∓ 15 m) 의 최대 종단·횡경사.
출력: 두 조건 최대 경사 합이 작은 순 상위."""
import json, math, sys
import numpy as np
from PIL import Image
from pathlib import Path
T = Path(sys.argv[1]); WSDF = Path(sys.argv[2]); OUT = sys.argv[3]
meta = json.load(open(T / "tiles.json")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]; ALT = meta["world_origin_alt_m"]; _img = {}
inc = set(l.split("model://")[1].split("<")[0] for l in WSDF.read_text().splitlines() if "model://T" in l)
def z_at(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); name = f"T{i:02d}_{j:02d}"; t = meta["tiles"][name]
    if name not in _img: _img[name] = np.asarray(Image.open(T / name / "heightmap.png"), dtype=np.float64)
    img = _img[name]; x0, y0, x1, y1 = t["bounds"]; n = img.shape[0] - 1
    fc, fr = (x - x0) / (x1 - x0) * n, (y1 - y) / (y1 - y0) * n; c0, r0 = min(int(fc), n - 1), min(int(fr), n - 1); dc, dr = fc - c0, fr - r0
    v = img[r0, c0] * (1 - dc) * (1 - dr) + img[r0, c0 + 1] * dc * (1 - dr) + img[r0 + 1, c0] * (1 - dc) * dr + img[r0 + 1, c0 + 1] * dc * dr
    return t["zmin"] + v / 65535.0 * t["span"] - ALT
def slope_max(xs, ys):
    g = 0.0
    for x in xs:
        for y in ys:
            gx = (z_at(x + 1, y) - z_at(x - 1, y)) / 2; gy = (z_at(x, y + 1) - z_at(x, y - 1)) / 2; g = max(g, math.hypot(gx, gy))
    return g
res = []
names = sorted(inc)
for nm in names:
    i, j = int(nm[1:3]), int(nm[4:6])
    quad = [f"T{i:02d}_{j:02d}", f"T{i+1:02d}_{j:02d}", f"T{i:02d}_{j+1:02d}", f"T{i+1:02d}_{j+1:02d}"]
    if not all(q in inc for q in quad): continue
    cx, cy = OX + (i + 1) * TM, OY + (j + 1) * TM
    gc = slope_max(np.arange(cx - 6, cx + 6.01, 1.5), np.arange(cy - 6, cy + 6.01, 1.5))
    lx = cx + 40.0; gy = slope_max([lx - 1.5, lx, lx + 1.5], np.arange(cy - 15, cy + 15.01, 1.5))
    res.append({"corner": [cx, cy], "tiles": quad, "corner_slope_max": round(gc, 4), "ylane_x": lx, "ylane_slope_max": round(gy, 4),
                "corner_z": round(z_at(cx + 0.01, cy + 0.01), 3)})
res.sort(key=lambda r: r["corner_slope_max"] + r["ylane_slope_max"])
json.dump({"n": len(res), "top": res[:15]}, open(OUT, "w"), indent=1)
print(len(res)); [print(json.dumps(r)) for r in res[:8]]
