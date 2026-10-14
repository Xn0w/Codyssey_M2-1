"""R0/R1 스폰 계산 (WSL python3, Gazebo 없음): yaw −2.5652 (원 주행 방위)·y 고정 (원 주행에서 차 중심이 x=4380 을 지날 때의 y), x 만 변경.
바퀴 중심 (차체 기준 ±1.35, ±0.8) 월드 x 와 빈 띠 [4379.512195, 4380.487805] (= 4380 ∓ 1000·1024/1025/2 와 타일 중심 차) 비교, 바퀴 접지 범위 x (반지름 0.35 · 폭 0.25 투영) 포함.
z = 차 중심 분석 지면 + 0.45 (기존 결정적 규칙)."""
import csv, json, math, sys
import numpy as np
from PIL import Image
from pathlib import Path
T = Path(sys.argv[1]); POSE = sys.argv[2]; OUT = sys.argv[3]
meta = json.load(open(T / "tiles.json")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]; ALT = meta["world_origin_alt_m"]; _img = {}
def z_at(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); name = f"T{i:02d}_{j:02d}"; t = meta["tiles"][name]
    if name not in _img: _img[name] = np.asarray(Image.open(T / name / "heightmap.png"), dtype=np.float64)
    img = _img[name]; x0, y0, x1, y1 = t["bounds"]; n = img.shape[0] - 1
    fc, fr = (x - x0) / (x1 - x0) * n, (y1 - y) / (y1 - y0) * n; c0, r0 = min(int(fc), n - 1), min(int(fr), n - 1); dc, dr = fc - c0, fr - r0
    v = img[r0, c0] * (1 - dc) * (1 - dr) + img[r0, c0 + 1] * dc * (1 - dr) + img[r0 + 1, c0] * (1 - dc) * dr + img[r0 + 1, c0 + 1] * dc * dr
    return name, t["zmin"] + v / 65535.0 * t["span"] - ALT
rows = [r for r in csv.DictReader(open(POSE))]
k = min(range(len(rows)), key=lambda i: abs(float(rows[i]["x"]) - 4380.0)); Y0 = round(float(rows[k]["y"]), 3)
PSI = -2.5652; c, s = math.cos(PSI), math.sin(PSI)
OFF = {"FL": (1.35, 0.8), "FR": (1.35, -0.8), "RL": (-1.35, 0.8), "RR": (-1.35, -0.8)}
HALF = 1000.0 * 1024 / 1025 / 2; BAND = (4880.0 - 500.0 - (500.0 - HALF), 3880.0 + HALF)        # T05 왼쪽 끝 = 4880 − 499.512, T04 오른쪽 끝 = 3880 + 499.512
BAND = (3880.0 + HALF, 4880.0 - HALF)
EXT = 0.35 * abs(c) + 0.125 * abs(s)                                                               # 바퀴 접지 범위 x 반폭 (진행 방향 반지름·폭 투영)
def wheels(cx):
    out = {}
    for k_, (bx, by) in OFF.items():
        wx, wy = cx + bx * c - by * s, Y0 + bx * s + by * c
        lo, hi = wx - EXT, wx + EXT
        out[k_] = {"x": round(wx, 4), "y": round(wy, 4), "x_patch": [round(lo, 4), round(hi, 4)], "tile_by_center": z_at(wx, wy)[0],
                   "in_band_center": BAND[0] < wx < BAND[1], "patch_overlaps_band": hi > BAND[0] and lo < BAND[1],
                   "patch_inside_band": lo > BAND[0] and hi < BAND[1], "ground_z": round(z_at(wx, wy)[1], 4)}
    return out
cases = {"R0a": 4400.0, "R0b": 4360.0}
cases["R1a"] = round(4380.0 - (OFF["FL"][0] * c - OFF["FL"][1] * s), 4)
cases["R1b"] = round(4380.0 - (OFF["FR"][0] * c - OFF["FR"][1] * s), 4)
res = {"y0": Y0, "yaw": PSI, "band_x": [round(BAND[0], 6), round(BAND[1], 6)], "band_width_m": round(BAND[1] - BAND[0], 6), "wheel_patch_half_x": round(EXT, 4), "cases": {}}
for name, cx in cases.items():
    g = z_at(cx, Y0)[1]; W_ = wheels(cx)
    res["cases"][name] = {"center_x": cx, "center_ground_z": round(g, 4), "spawn": f"{cx},{Y0},{round(g + 0.45, 3)},{PSI}", "wheels": W_,
                          "wheels_ground_spread_m": round(max(w["ground_z"] for w in W_.values()) - min(w["ground_z"] for w in W_.values()), 4)}
json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
for n_, v in res["cases"].items():
    print(n_, v["spawn"], {k_: (w["x"], w["tile_by_center"], w["in_band_center"], w["patch_inside_band"], w["patch_overlaps_band"]) for k_, w in v["wheels"].items()}, "spread", v["wheels_ground_spread_m"])
print("band", res["band_x"], res["band_width_m"], "y0", Y0)
