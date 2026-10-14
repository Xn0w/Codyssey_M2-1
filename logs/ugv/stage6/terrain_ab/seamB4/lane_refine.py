"""상위 모서리에서 Y 경계 통과 직선 위치 재탐색 (WSL): 모서리 x ± 20~300 m (모서리 10 m 이내 제외), 남북 직선 y = 경계 ∓ 15 m, 폭 ±1.5 m 최대 경사.
모서리 정지 영역은 ±3.5 m (차량 반 대각 ≈ 2.4 m + 여유)."""
import json, math, sys
import numpy as np
from PIL import Image
from pathlib import Path
T = Path(sys.argv[1]); C = json.load(open(sys.argv[2]))["top"][:3]; OUT = sys.argv[3]
meta = json.load(open(T / "tiles.json")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]; ALT = meta["world_origin_alt_m"]; _img = {}
def z_at(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); name = f"T{i:02d}_{j:02d}"; t = meta["tiles"][name]
    if name not in _img: _img[name] = np.asarray(Image.open(T / name / "heightmap.png"), dtype=np.float64)
    img = _img[name]; x0, y0, x1, y1 = t["bounds"]; n = img.shape[0] - 1
    fc, fr = (x - x0) / (x1 - x0) * n, (y1 - y) / (y1 - y0) * n; c0, r0 = min(int(fc), n - 1), min(int(fr), n - 1); dc, dr = fc - c0, fr - r0
    v = img[r0, c0] * (1 - dc) * (1 - dr) + img[r0, c0 + 1] * dc * (1 - dr) + img[r0 + 1, c0] * (1 - dc) * dr + img[r0 + 1, c0 + 1] * dc * dr
    return t["zmin"] + v / 65535.0 * t["span"] - ALT
def smax(xs, ys):
    g = 0.0
    for x in xs:
        for y in ys:
            g = max(g, math.hypot((z_at(x + 1, y) - z_at(x - 1, y)) / 2, (z_at(x, y + 1) - z_at(x, y - 1)) / 2))
    return g
out = []
for c in C:
    cx, cy = c["corner"]
    gc = smax(np.arange(cx - 3.5, cx + 3.51, 0.7), np.arange(cy - 3.5, cy + 3.51, 0.7))
    best = []
    for dx in list(range(-300, -19, 5)) + list(range(20, 301, 5)):
        lx = cx + dx; g = smax([lx - 1.5, lx, lx + 1.5], np.arange(cy - 15, cy + 15.01, 1.0)); best.append((g, lx))
    best.sort(); out.append({"corner": c["corner"], "tiles": c["tiles"], "corner_slope_max_3p5": round(gc, 4), "lanes_best": [{"x": lx, "slope_max": round(g, 4)} for g, lx in best[:5]]})
json.dump(out, open(OUT, "w"), indent=1); [print(json.dumps(o)) for o in out]
