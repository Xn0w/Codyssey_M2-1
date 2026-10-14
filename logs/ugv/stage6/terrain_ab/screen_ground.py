"""실제 지형 선별 접지·차체 상태 (WSL, Gazebo 없이 기록 분석): gz 기록기 pose.csv 의 모델 원점 z − 지면 높이 (타일 높이장 쌍선형), 롤·피치.
기준 근거 (사전): 기존 s3113 평지 출발 기록에서 모델 원점 z − 지면 ≈ +0.003 m (스폰 = 지면 + 0.45 에서 내려앉음).
사용: python3 screen_ground.py <tiles_v2> <gzrec_dir> <out.json>"""
import csv, json, math, sys
import numpy as np
from PIL import Image
from pathlib import Path
T = Path(sys.argv[1]); R = Path(sys.argv[2]); OUT = Path(sys.argv[3])
meta = json.load(open(T / "tiles.json", encoding="utf-8")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]; ALT = meta["world_origin_alt_m"]; _img = {}
def z_at(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); name = f"T{i:02d}_{j:02d}"; t = meta["tiles"][name]
    if name not in _img: _img[name] = np.asarray(Image.open(T / name / "heightmap.png"), dtype=np.float64)
    img = _img[name]; x0, y0, x1, y1 = t["bounds"]; n = img.shape[0] - 1
    fc, fr = (x - x0) / (x1 - x0) * n, (y1 - y) / (y1 - y0) * n; c0, r0 = min(int(fc), n - 1), min(int(fr), n - 1); dc, dr = fc - c0, fr - r0
    v = img[r0, c0] * (1 - dc) * (1 - dr) + img[r0, c0 + 1] * dc * (1 - dr) + img[r0 + 1, c0] * (1 - dc) * dr + img[r0 + 1, c0 + 1] * dc * dr
    return name, t["zmin"] + v / 65535.0 * t["span"] - ALT
rows = [r for r in csv.DictReader(open(R / "pose.csv"))][::25]            # 약 0.5 s 간격으로 솎음
out, prev = [], None
for r in rows:
    t, x, y, z = float(r["stamp"]), float(r["x"]), float(r["y"]), float(r["z"]); qw, qx, qy, qz = (float(r[k]) for k in ("qw", "qx", "qy", "qz"))
    roll = math.degrees(math.atan2(2 * (qw * qx + qy * qz), 1 - 2 * (qx * qx + qy * qy))); pitch = math.degrees(math.asin(max(-1, min(1, 2 * (qw * qy - qz * qx)))))
    tile, g = z_at(x, y); v = None if prev is None else math.dist((x, y), prev[1:3]) / max(1e-6, t - prev[0]); prev = (t, x, y)
    out.append({"t": t, "tile": tile, "dz": round(z - g, 4), "roll": round(roll, 2), "pitch": round(pitch, 2), "v": None if v is None else round(v, 2)})
dz = [o["dz"] for o in out]; rest = [o for o in out if o["v"] is not None and o["v"] < 0.05]
res = {"n": len(out), "dz_min": min(dz), "dz_max": max(dz), "rest_dz": [rest[0]["dz"], rest[-1]["dz"]] if rest else None,
       "rest_first_t": rest[0]["t"] if rest else None, "rest_last_t": rest[-1]["t"] if rest else None,
       "roll_abs_max": max(abs(o["roll"]) for o in out), "pitch_abs_max": max(abs(o["pitch"]) for o in out),
       "tiles_seen": sorted({o["tile"] for o in out}), "baseline_note": "s3113 평지 출발 원점 z − 지면 ≈ +0.003 m", "series": out}
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "series"}, ensure_ascii=False))
