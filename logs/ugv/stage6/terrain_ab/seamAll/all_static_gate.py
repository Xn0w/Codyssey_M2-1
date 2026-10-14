"""tiles_v2c1 전체 정적 게이트 (WSL python3, Gazebo 없음): 타일별 (PNG 해시·pose·visual size·수직 size 불변, N 1025·sampling 없음, 충돌 꼭짓점 = PNG 좌표 −500 + i·1000/1024 (X·Y)),
인접 공유 가장자리 전부 (X·Y: 틈·높이 차 최대/ p99), 네 타일 모서리 전부 (높이 차). 사용: python3 all_static_gate.py <tiles_v2> <tiles_v2c1> <out.json>"""
import json, re, sys, hashlib
import numpy as np
from PIL import Image
from pathlib import Path
O = Path(sys.argv[1]); C = Path(sys.argv[2]); OUT = sys.argv[3]
meta = json.load(open(O / "tiles.json")); ALT = meta["world_origin_alt_m"]
def parse(p):
    s = p.read_text(encoding="utf-8")
    col = re.search(r'<collision name="collision"><geometry><heightmap><uri>[^<]+</uri><size>([^<]+)</size>', s); vis = re.search(r'<visual name="visual"><geometry><heightmap><uri>[^<]+</uri><size>([^<]+)</size>', s)
    return list(map(float, re.search(r"<pose>([^<]+)</pose>", s).group(1).split())), list(map(float, col.group(1).split())), list(map(float, vis.group(1).split())), "<sampling>" in s
names = sorted(meta["tiles"]); bad = []; Z = {}; P = {}; H = {}
for t in names:
    po, co, vo, _ = parse(O / t / "model.sdf"); pc, cc, vc, smp = parse(C / t / "model.sdf")
    img = np.asarray(Image.open(C / t / "heightmap.png")); N = img.shape[0]
    same = hashlib.sha1((O / t / "heightmap.png").read_bytes()).hexdigest() == hashlib.sha1((C / t / "heightmap.png").read_bytes()).hexdigest()
    sc = cc[0] / N; half = (N - 1) * sc / 2; off = max(abs(-half + i * sc - (-500 + i * 1000 / 1024)) for i in (0, 256, 512, 768, 1024))
    sc_y = cc[1] / N; off_y = max(abs(-(N - 1) * sc_y / 2 + i * sc_y - (-500 + i * 1000 / 1024)) for i in (0, 512, 1024))
    if not (N == 1025 and not smp and same and po == pc and vo == vc and co[2] == cc[2] and off < 1e-9 and off_y < 1e-9): bad.append(t)
    tm = meta["tiles"][t]; Z[t] = tm["zmin"] + img.astype(np.float64) / 65535.0 * tm["span"] - ALT; P[t] = pc; H[t] = half
idx = {(int(t[1:3]), int(t[4:6])): t for t in names}
edges = []
for (i, j), t in idx.items():
    if (i + 1, j) in idx:
        u = idx[(i + 1, j)]; g = (P[u][0] - H[u]) - (P[t][0] + H[t]); e = np.abs(Z[t][:, -1] - Z[u][:, 0]); edges.append(("x", t, u, g, float(e.max()), float(np.percentile(e, 99))))
    if (i, j + 1) in idx:
        u = idx[(i, j + 1)]; g = (P[u][1] - H[u]) - (P[t][1] + H[t]); e = np.abs(Z[t][0, :] - Z[u][-1, :]); edges.append(("y", t, u, g, float(e.max()), float(np.percentile(e, 99))))
corners = []
for (i, j), t in idx.items():
    q = [(i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1)]
    if all(k in idx for k in q):
        v = [Z[idx[q[0]]][0, -1], Z[idx[q[1]]][0, 0], Z[idx[q[2]]][-1, -1], Z[idx[q[3]]][-1, 0]]; corners.append((t, float(max(v) - min(v))))
gmax = max(abs(e[3]) for e in edges); hmax = max(e[4] for e in edges); cmax = max(c[1] for c in corners)
worst = sorted(edges, key=lambda e: -e[4])[:8]
res = {"n_tiles": len(names), "tile_check_fail": bad, "n_edges": len(edges), "edge_gap_abs_max_m": gmax, "edge_height_diff_max_m": round(hmax, 4),
       "edge_height_diff_p99_of_max": round(float(np.percentile([e[4] for e in edges], 99)), 4), "worst_edges": [[e[0], e[1], e[2], round(e[4], 4)] for e in worst],
       "n_corners": len(corners), "corner_spread_max_m": round(cmax, 4), "rule": "PASS = 타일 검사 실패 0·틈 |·| < 1e-9·가장자리 높이 차 ≤ 0.01·모서리 ≤ 0.01"}
res["status"] = "PASS" if not bad and gmax < 1e-9 and hmax <= 0.01 and cmax <= 0.01 else "FAIL"
json.dump(res, open(OUT, "w"), indent=1); print(json.dumps({k: v for k, v in res.items() if k != "worst_edges"}), res["worst_edges"][:4])
