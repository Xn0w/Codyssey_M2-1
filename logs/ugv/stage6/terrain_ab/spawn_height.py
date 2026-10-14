"""타일 높이장에서 지면 높이 (월드 z = 높이 − world_origin_alt_m). 검증: 기존 스폰 파일 z 와 비교. 사용: python3 spawn_height.py <tiles_v2> x,y[,ref_z] ..."""
import json, math, sys
import numpy as np
from PIL import Image
from pathlib import Path
T = Path(sys.argv[1]); meta = json.load(open(T / "tiles.json")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]; ALT = meta["world_origin_alt_m"]
def z_at(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); name = f"T{i:02d}_{j:02d}"; t = meta["tiles"][name]
    x0, y0, x1, y1 = t["bounds"]; img = np.asarray(Image.open(T / name / "heightmap.png"), dtype=np.float64); n = img.shape[0] - 1
    fc, fr = (x - x0) / (x1 - x0) * n, (y1 - y) / (y1 - y0) * n          # 열 = 서→동, 행 0 = 북
    c0, r0 = int(fc), int(fr); dc, dr = fc - c0, fr - r0
    v = (img[r0, c0] * (1 - dc) * (1 - dr) + img[r0, c0 + 1] * dc * (1 - dr) + img[r0 + 1, c0] * (1 - dc) * dr + img[r0 + 1, c0 + 1] * dc * dr)
    return name, t["zmin"] + v / 65535.0 * t["span"] - ALT
for a in sys.argv[2:]:
    p = list(map(float, a.split(","))); name, z = z_at(p[0], p[1])
    print(json.dumps({"xy": p[:2], "tile": name, "ground_z": round(z, 3), "ref_spawn_z": p[2] if len(p) > 2 else None,
                      "ref_minus_ground": round(p[2] - z, 3) if len(p) > 2 else None}))
