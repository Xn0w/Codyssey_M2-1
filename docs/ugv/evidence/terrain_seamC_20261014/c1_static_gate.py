"""후보 c1 정적 게이트 (WSL python3, Gazebo 없음, Codex 0920 2절). 상류 전달식 (SRC_chain.md) 로 충돌 꼭짓점 월드 좌표를 계산해
분석/시각 PNG 좌표 (pose − 500 + i·1000/1024) 와 X·Y 양축·네 모서리·내부 대표점·경계 양쪽 비교. 높이·pose·PNG·zmin/span 불변, 공유 가장자리 높이 연속.
사용: python3 c1_static_gate.py <tiles_v2> <tiles_c1> <out.json>"""
import json, re, sys, hashlib
import numpy as np
from PIL import Image
from pathlib import Path
O = Path(sys.argv[1]); C = Path(sys.argv[2]); OUT = sys.argv[3]
meta = json.load(open(O / "tiles.json")); ALT = meta["world_origin_alt_m"]
def parse(p):
    s = p.read_text(encoding="utf-8")
    pose = list(map(float, re.search(r"<pose>([^<]+)</pose>", s).group(1).split()))
    col = re.search(r'<collision name="collision"><geometry><heightmap><uri>([^<]+)</uri><size>([^<]+)</size><pos>([^<]+)</pos>', s)
    vis = re.search(r'<visual name="visual"><geometry><heightmap><uri>([^<]+)</uri><size>([^<]+)</size><pos>([^<]+)</pos>', s)
    return {"pose": pose, "col_size": list(map(float, col.group(2).split())), "col_pos": col.group(3), "vis_size": list(map(float, vis.group(2).split())),
            "sampling": "<sampling>" in s, "col_uri": col.group(1), "vis_uri": vis.group(1)}
res = {"tiles": {}, "checks": {}}; ok = True
cols = {}
for t in ("T04_16", "T05_16"):
    o, c = parse(O / t / "model.sdf"), parse(C / t / "model.sdf")
    img = np.asarray(Image.open(C / t / "heightmap.png")); N = img.shape[0]
    same_png = hashlib.sha1((O / t / "heightmap.png").read_bytes()).hexdigest() == hashlib.sha1((C / t / "heightmap.png").read_bytes()).hexdigest()
    s = 1; V = N * s - s + 1
    def verts(size):   # 상류 식: scale = size/V, ODE 폭 = (V−1)·scale, 중심 기준 → 꼭짓점 i 국소 = −폭/2 + i·scale
        sc = size / V; wdt = (V - 1) * sc; return np.array([-wdt / 2 + i * sc for i in range(V)]), sc, wdt
    vx_c, sc_c, w_c = verts(c["col_size"][0]); vy_c, _, _ = verts(c["col_size"][1]); vx_o, sc_o, w_o = verts(o["col_size"][0])
    ref = np.array([-500.0 + i * 1000.0 / 1024 for i in range(V)])
    dx_c, dy_c, dx_o = np.abs(vx_c - ref), np.abs(vy_c - ref), np.abs(vx_o - ref)
    t_meta = meta["tiles"][t]
    rec = {"N": int(N), "dtype": str(img.dtype), "sampling_tag_present": c["sampling"], "png_same_as_orig": same_png,
           "pose_same": o["pose"] == c["pose"], "vis_size_same": o["vis_size"] == c["vis_size"] == [1000.0, 1000.0, o["vis_size"][2]],
           "col_z_size_same": o["col_size"][2] == c["col_size"][2], "col_xy_size": c["col_size"][:2],
           "orig": {"scale": sc_o, "width": w_o, "half": w_o / 2, "max_vertex_offset_vs_png_m": float(dx_o.max())},
           "cand": {"scale": sc_c, "width": w_c, "half": w_c / 2, "max_vertex_offset_x_m": float(dx_c.max()), "max_vertex_offset_y_m": float(dy_c.max())},
           "sample_points": {name: {"i": i, "local_cand": round(float(vx_c[i]), 9), "local_png": round(float(ref[i]), 9)} for name, i in (("corner0", 0), ("q1", 256), ("center", 512), ("q3", 768), ("corner1", 1024))}}
    res["tiles"][t] = rec
    ok &= rec["N"] == 1025 and not rec["sampling_tag_present"] and same_png and rec["pose_same"] and rec["vis_size_same"] and rec["col_z_size_same"] \
        and rec["cand"]["max_vertex_offset_x_m"] < 1e-9 and rec["cand"]["max_vertex_offset_y_m"] < 1e-9
    z = t_meta["zmin"] + img.astype(np.float64) / 65535.0 * t_meta["span"] - ALT
    cols[t] = z
# 공유 가장자리 x = 4380: T04 마지막 열 (i=1024) ↔ T05 첫 열 (i=0), 같은 행 (j 동일 — 두 타일 bounds y 같음)
e = np.abs(cols["T04_16"][:, -1] - cols["T05_16"][:, 0])
x_t04_last = res["tiles"]["T04_16"]["sample_points"]["corner1"]["local_cand"] + 3880.0
x_t05_first = res["tiles"]["T05_16"]["sample_points"]["corner0"]["local_cand"] + 4880.0
res["checks"] = {"all_tile_checks": bool(ok), "shared_edge_x": [x_t04_last, x_t05_first], "shared_edge_gap_m": round(x_t05_first - x_t04_last, 12),
                 "shared_edge_height_diff_max_m": round(float(e.max()), 4), "shared_edge_height_diff_p99_m": round(float(np.percentile(e, 99)), 4),
                 "orig_gap_m": round((4880.0 - res["tiles"]["T05_16"]["orig"]["half"]) - (3880.0 + res["tiles"]["T04_16"]["orig"]["half"]), 6),
                 "note": "꼭짓점 좌표는 상류 소스 전달식 기반 계산 — 실제 엔진 반영은 후보 기동 시 AABB 로그 (반폭 500.000 기대) 와 R0/R1 접촉으로 확인"}
res["status"] = "PASS" if ok and abs(res["checks"]["shared_edge_gap_m"]) < 1e-9 and res["checks"]["shared_edge_height_diff_max_m"] <= 0.01 else "FAIL"
json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
print(res["status"], json.dumps(res["checks"], ensure_ascii=False)); [print(t, {k: v for k, v in r.items() if k != "sample_points"}) for t, r in res["tiles"].items()]
