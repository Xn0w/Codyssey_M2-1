"""B 단계 4 타일 후보 정적 게이트 (WSL python3): c1_static_gate 일반화 — 타일별 (N·sampling·PNG·pose·visual·수직 size 불변, 충돌 꼭짓점 X·Y = PNG 좌표),
공유 가장자리 4 쌍 (X 경계 2: 서↔동, Y 경계 2: 남↔북) 틈·높이 차, 네 타일 모서리 점 높이 일치. 사용: python3 b4_static_gate.py <tiles_v2> <tiles_cand> <out.json> T15_05 T16_05 T15_06 T16_06"""
import json, re, sys, hashlib
import numpy as np
from PIL import Image
from pathlib import Path
O = Path(sys.argv[1]); C = Path(sys.argv[2]); OUT = sys.argv[3]; SW, SE, NW, NE = sys.argv[4:8]
meta = json.load(open(O / "tiles.json")); ALT = meta["world_origin_alt_m"]
def parse(p):
    s = p.read_text(encoding="utf-8")
    col = re.search(r'<collision name="collision"><geometry><heightmap><uri>[^<]+</uri><size>([^<]+)</size>', s); vis = re.search(r'<visual name="visual"><geometry><heightmap><uri>[^<]+</uri><size>([^<]+)</size>', s)
    return {"pose": list(map(float, re.search(r"<pose>([^<]+)</pose>", s).group(1).split())), "col": list(map(float, col.group(1).split())), "vis": list(map(float, vis.group(1).split())), "sampling": "<sampling>" in s}
res = {"tiles": {}, "edges": {}}; ok = True; Z = {}; P = {}
for t in (SW, SE, NW, NE):
    o, c = parse(O / t / "model.sdf"), parse(C / t / "model.sdf"); img = np.asarray(Image.open(C / t / "heightmap.png")); N = img.shape[0]; V = N
    same = hashlib.sha1((O / t / "heightmap.png").read_bytes()).hexdigest() == hashlib.sha1((C / t / "heightmap.png").read_bytes()).hexdigest()
    ref = np.array([-500.0 + i * 1000.0 / 1024 for i in range(V)])
    vx = np.array([-((V - 1) * c["col"][0] / V) / 2 + i * c["col"][0] / V for i in range(V)]); vy = np.array([-((V - 1) * c["col"][1] / V) / 2 + i * c["col"][1] / V for i in range(V)])
    r = {"N": int(N), "sampling_tag": c["sampling"], "png_same": same, "pose_same": o["pose"] == c["pose"], "vis_same": o["vis"] == c["vis"], "z_size_same": o["col"][2] == c["col"][2],
         "col_xy": c["col"][:2], "max_off_x": float(np.abs(vx - ref).max()), "max_off_y": float(np.abs(vy - ref).max()), "half": (V - 1) * c["col"][0] / V / 2}
    res["tiles"][t] = r; ok &= N == 1025 and not r["sampling_tag"] and same and r["pose_same"] and r["vis_same"] and r["z_size_same"] and r["max_off_x"] < 1e-9 and r["max_off_y"] < 1e-9
    tm = meta["tiles"][t]; Z[t] = tm["zmin"] + img.astype(np.float64) / 65535.0 * tm["span"] - ALT; P[t] = c["pose"]
def edge(a, b, axis):   # axis x: a 서, b 동 → a 마지막 열 vs b 첫 열 / axis y: a 남, b 북 → PNG 행 0 = 북 → a 첫 행 (북쪽 끝) vs b 마지막 행 (남쪽 끝)
    if axis == "x": da, db = Z[a][:, -1], Z[b][:, 0]; ga = P[a][0] + res["tiles"][a]["half"]; gb = P[b][0] - res["tiles"][b]["half"]
    else: da, db = Z[a][0, :], Z[b][-1, :]; ga = P[a][1] + res["tiles"][a]["half"]; gb = P[b][1] - res["tiles"][b]["half"]
    e = np.abs(da - db); return {"gap_m": round(gb - ga, 9), "height_diff_max": round(float(e.max()), 4), "height_diff_p99": round(float(np.percentile(e, 99)), 4)}
res["edges"] = {f"{SW}|{SE} (x)": edge(SW, SE, "x"), f"{NW}|{NE} (x)": edge(NW, NE, "x"), f"{SW}|{NW} (y)": edge(SW, NW, "y"), f"{SE}|{NE} (y)": edge(SE, NE, "y")}
corner = {SW: Z[SW][0, -1], SE: Z[SE][0, 0], NW: Z[NW][-1, -1], NE: Z[NE][-1, 0]}
res["corner_heights"] = {k: round(float(v), 4) for k, v in corner.items()}; res["corner_spread_m"] = round(float(max(corner.values()) - min(corner.values())), 4)
eok = all(abs(e["gap_m"]) < 1e-9 and e["height_diff_max"] <= 0.01 for e in res["edges"].values()) and res["corner_spread_m"] <= 0.01
res["status"] = "PASS" if ok and eok else "FAIL"
json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1); print(res["status"], json.dumps(res["edges"]), res["corner_heights"], res["corner_spread_m"])
for t, r in res["tiles"].items(): print(t, r)
