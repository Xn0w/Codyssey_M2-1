"""전 타일 보정 월드 진단 4 회 스폰 (WSL): z = 중심 분석 지면 + 0.45, 바퀴 시작 좌표·타일·경계 띠 판별 기록."""
import json, math, sys
import numpy as np
from PIL import Image
from pathlib import Path
T = Path(sys.argv[1]); OUT = sys.argv[2]
meta = json.load(open(T / "tiles.json")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]; ALT = meta["world_origin_alt_m"]; _img = {}
def z_at(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); name = f"T{i:02d}_{j:02d}"; t = meta["tiles"][name]
    if name not in _img: _img[name] = np.asarray(Image.open(T / name / "heightmap.png"), dtype=np.float64)
    img = _img[name]; x0, y0, x1, y1 = t["bounds"]; n = img.shape[0] - 1
    fc, fr = (x - x0) / (x1 - x0) * n, (y1 - y) / (y1 - y0) * n; c0, r0 = min(int(fc), n - 1), min(int(fr), n - 1); dc, dr = fc - c0, fr - r0
    v = img[r0, c0] * (1 - dc) * (1 - dr) + img[r0, c0 + 1] * dc * (1 - dr) + img[r0 + 1, c0] * (1 - dc) * dr + img[r0 + 1, c0 + 1] * dc * dr
    return name, t["zmin"] + v / 65535.0 * t["span"] - ALT
cases = {"a1_revX": (4372.0, 5922.401, 0.5764), "a2_obliqX": (4372.5, 5922.4, 0.7854), "a3_stopY": (15400.8, -4632.35, math.pi / 2), "a4_corner": (15380.8, -4632.35, math.pi / 2)}
OFF = {"FL": (1.35, 0.8), "FR": (1.35, -0.8), "RL": (-1.35, 0.8), "RR": (-1.35, -0.8)}; res = {}
for k, (cx, cy, yaw) in cases.items():
    c, s = math.cos(yaw), math.sin(yaw); W = {w: [round(cx + bx * c - by * s, 3), round(cy + bx * s + by * c, 3)] for w, (bx, by) in OFF.items()}
    gz = [z_at(*p)[1] for p in W.values()]
    res[k] = {"spawn": f"{cx},{cy},{round(z_at(cx, cy)[1] + 0.45, 3)},{round(yaw, 6)}", "wheels": W, "wheel_tiles": {w: z_at(*p)[0] for w, p in W.items()}, "wheel_ground_spread": round(max(gz) - min(gz), 4)}
json.dump(res, open(OUT, "w"), indent=1); [print(k, v["spawn"], v["wheel_tiles"], v["wheel_ground_spread"]) for k, v in res.items()]
