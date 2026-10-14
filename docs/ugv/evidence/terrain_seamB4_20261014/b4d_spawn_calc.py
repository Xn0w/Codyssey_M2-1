"""B 단계 스폰 계산 (WSL): yaw π/2 (북쪽), 바퀴 중심 = 중심 + R(yaw)·(±1.35, ±0.8). 원 띠 (보정 전 충돌 틈): X 경계 x=15380 ±0.487805, Y 경계 y=−4631 ±0.487805.
바퀴 접지 범위 반폭: 진행 방향 (y) 0.35, 옆 (x) 0.125. z = 중심 분석 지면 + 0.45."""
import json, math, sys
import numpy as np
from PIL import Image
from pathlib import Path
T = Path(sys.argv[1]); OUT = sys.argv[2]; EXTRA = sys.argv[3:]   # (d) 추가 회차 "이름=cx,cy"
meta = json.load(open(T / "tiles.json")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]; ALT = meta["world_origin_alt_m"]; _img = {}
def z_at(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); name = f"T{i:02d}_{j:02d}"; t = meta["tiles"][name]
    if name not in _img: _img[name] = np.asarray(Image.open(T / name / "heightmap.png"), dtype=np.float64)
    img = _img[name]; x0, y0, x1, y1 = t["bounds"]; n = img.shape[0] - 1
    fc, fr = (x - x0) / (x1 - x0) * n, (y1 - y) / (y1 - y0) * n; c0, r0 = min(int(fc), n - 1), min(int(fr), n - 1); dc, dr = fc - c0, fr - r0
    v = img[r0, c0] * (1 - dc) * (1 - dr) + img[r0, c0 + 1] * dc * (1 - dr) + img[r0 + 1, c0] * (1 - dc) * dr + img[r0 + 1, c0 + 1] * dc * dr
    return name, t["zmin"] + v / 65535.0 * t["span"] - ALT
YAW = math.pi / 2; c, s = math.cos(YAW), math.sin(YAW); H = 1000.0 * 1024 / 1025 / 2
BX = (15380.0 - (500 - H), 15380.0 + (500 - H)); BY = (-4631.0 - (500 - H), -4631.0 + (500 - H))
OFF = {"FL": (1.35, 0.8), "FR": (1.35, -0.8), "RL": (-1.35, 0.8), "RR": (-1.35, -0.8)}
cases = {"bR0": (15400.8, -4645.0), "bR1y": (15400.8, -4632.35), "bR1c": (15380.8, -4632.35), "bR2y_start": (15400.8, -4640.0)}
for e in EXTRA:
    k_, v_ = e.split("="); cases[k_] = tuple(map(float, v_.split(",")))
res = {"yaw": round(YAW, 6), "band_x": BX, "band_y": BY, "cases": {}}
for k, (cx, cy) in cases.items():
    g = z_at(cx, cy)[1]; W = {}
    for w, (bx, by) in OFF.items():
        wx, wy = cx + bx * c - by * s, cy + bx * s + by * c
        W[w] = {"x": round(wx, 4), "y": round(wy, 4), "tile": z_at(wx, wy)[0], "in_band_x": BX[0] - 0.125 < wx < BX[1] + 0.125, "in_band_y": BY[0] - 0.35 < wy < BY[1] + 0.35,
                "patch_inside_band_y": BY[0] < wy - 0.35 and wy + 0.35 < BY[1], "ground_z": round(z_at(wx, wy)[1], 4)}
    res["cases"][k] = {"center": [cx, cy], "spawn": f"{cx},{cy},{round(g + 0.45, 3)},{round(YAW, 6)}", "wheels": W,
                        "wheel_ground_spread": round(max(v["ground_z"] for v in W.values()) - min(v["ground_z"] for v in W.values()), 4)}
json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
for k, v in res["cases"].items(): print(k, v["spawn"], {w: (x["x"], x["y"], x["tile"], x["in_band_x"], x["patch_inside_band_y"]) for w, x in v["wheels"].items()}, v["wheel_ground_spread"])
