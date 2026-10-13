import json, sys
import numpy as np
from PIL import Image
from pathlib import Path
T = Path(sys.argv[1]); meta = json.load(open(T / "tiles.json"))
sub = json.load(open(T / "road_subset_ab_route_v1.json")); tiles = set(sub["tiles"])
def hm(t):
    m = meta["tiles"][t]; return np.asarray(Image.open(T / t / "heightmap.png"), dtype=np.float64) * m["q_m"] + m["zmin"]
res = {}
for name, (di, dj, fa, fb) in {
    "E_lastcol_vs_firstcol": (1, 0, lambda A: A[:, -1], lambda B: B[:, 0]),
    "N_toprow_vs_bottomrow": (0, 1, lambda A: A[0, :], lambda B: B[-1, :]),
    "N_bottomrow_vs_toprow": (0, 1, lambda A: A[-1, :], lambda B: B[0, :]),
}.items():
    w, worst_pair, vals = 0, None, []
    for t in sorted(tiles):
        i, j = int(t[1:3]), int(t[4:6]); u = f"T{i+di:02d}_{j+dj:02d}"
        if u not in tiles: continue
        d = float(np.max(np.abs(fa(hm(t)) - fb(hm(u))))); vals.append(d)
        if d > w: w, worst_pair = d, (t, u)
    res[name] = {"pairs": len(vals), "max": round(w, 4), "median": round(float(np.median(vals)), 4), "worst": worst_pair}
print(json.dumps(res))
# PNG 메타: 비트 깊이·크기
im = Image.open(T / sorted(tiles)[0] / "heightmap.png"); print(im.mode, im.size, meta["tiles"][sorted(tiles)[0]]["q_m"])
