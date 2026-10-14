"""Fable 원인 분리 (읽기 전용 분석) — 정적 자산 대조.
1) gz-server.log 의 'ODE Heightfield AABB' 160 줄 (엔진이 실제로 만든 충돌 높이장 범위) ↔ tiles.json span / model.sdf size
2) T04_16·T05_16 PNG 통계·이음매 열 대조 (m 단위)
3) 스폰 지점 방향 변형 4 가지 ↔ 정지 회차 관측 z (방향 규약 확인)
4) 분석기 격자(1025 점/1000 m) ↔ 엔진 격자 가설(1024 점, 간격 1000/1024, 반폭 499.512) 높이 차
사용: python static_assets_check.py <tiles_v2> <gz-server.log 사본 또는 추출 txt> <out.json>
"""
import json, math, re, sys
import numpy as np
from PIL import Image
from pathlib import Path

T = Path(sys.argv[1]); LOG = Path(sys.argv[2]); OUT = Path(sys.argv[3])
meta = json.load(open(T / "tiles.json", encoding="utf-8")); ALT = meta["world_origin_alt_m"]; TM = meta["tile_m"]
world = (T / "ab_route_v1.sdf").read_text(encoding="utf-8")
order = re.findall(r"model://(T\d\d_\d\d)", world)
res = {"world_tiles_in_order": len(order)}

# 1) AABB 줄
txt = LOG.read_text(encoding="utf-8", errors="replace")
aabb = [(float(a), float(b), float(c), float(d), float(e), float(f)) for a, b, c, d, e, f in
        re.findall(r"ODE Heightfield AABB: min = \{([-\d.e+]+), ([-\d.e+]+), ([-\d.e+]+)\} max = \{([-\d.e+]+), ([-\d.e+]+), ([-\d.e+]+)\}", txt)]
# 첫 세션(첫 월드 기동)의 160 줄만
aabb = aabb[:160]
res["aabb_lines"] = len(aabb)
if aabb:
    xs = sorted({round(a[0], 3) for a in aabb} | {round(a[3], 3) for a in aabb}); zmins = sorted({round(a[2], 3) for a in aabb})
    res["aabb_half_extent_values"] = xs; res["aabb_zmin_values"] = zmins
    zmax = [a[5] for a in aabb]
    spans = [meta["tiles"][n]["span"] for n in order]
    res["zmax_vs_span_in_order"] = [{"tile": n, "span": round(s, 3), "aabb_zmax": round(z, 3), "ratio": round(z / s, 4)} for n, s, z in zip(order, spans, zmax)][:12]
    srt_z, srt_s = sorted(zmax), sorted(spans)
    res["zmax_sorted_vs_span_sorted_maxabs"] = round(max(abs(a - b) for a, b in zip(srt_z, srt_s)), 3)
    # 다른 가설: zmax = span * (maxpix/65535) / ((maxpix-minpix)/65535) ... 또는 zmax = span 인 타일 수
    res["n_zmax_equals_span_pm_0_01"] = sum(1 for n, z in zip(order, zmax) if abs(z - meta["tiles"][n]["span"]) < 0.01)
    # 각 타일 PNG 의 최대/최소 픽셀로 가설 검사 (처음 12 타일 + 대상 2 타일)
    chk = []
    for n, z in list(zip(order, zmax)):
        if n not in order[:12] + ["T04_16", "T05_16"]:
            continue
        img = np.asarray(Image.open(T / n / "heightmap.png"))
        mx, mn = int(img.max()), int(img.min()); sp = meta["tiles"][n]["span"]
        chk.append({"tile": n, "pix_min": mn, "pix_max": mx, "span": round(sp, 3), "aabb_zmax": round(z, 3),
                    "h_if_span*max/65535": round(sp * mx / 65535, 3), "zmax/span": round(z / sp, 4)})
    res["pixel_check"] = chk

# 2) 대상 타일 PNG·이음매
def grid_m(n):
    t = meta["tiles"][n]; img = np.asarray(Image.open(T / n / "heightmap.png"), dtype=np.float64)
    return t["zmin"] + img / 65535.0 * t["span"] - ALT, img
A, Ai = grid_m("T04_16"); B, Bi = grid_m("T05_16")
res["png"] = {"T04_16": {"shape": list(Ai.shape), "dtype": str(Ai.dtype), "pix_min": int(Ai.min()), "pix_max": int(Ai.max())},
              "T05_16": {"shape": list(Bi.shape), "dtype": str(Bi.dtype), "pix_min": int(Bi.min()), "pix_max": int(Bi.max())}}
d = A[:, -1] - B[:, 0]           # T04_16 동쪽 끝 열 ↔ T05_16 서쪽 끝 열 (같은 월드 x=4380, 행 0 = 북)
y_of_row = lambda r: 6369.0 - r * (TM / 1024)
rows_route = [r for r in range(1025) if abs(y_of_row(r) - 5954.0) < 60]
res["seam_x4380"] = {"max_abs_m": round(float(np.max(np.abs(d))), 4), "median_abs_m": round(float(np.median(np.abs(d))), 4),
                     "route_rows_y5894_6014_max_abs_m": round(float(np.max(np.abs(d[rows_route]))), 4),
                     "q_m": [meta["tiles"]["T04_16"]["q_m"], meta["tiles"]["T05_16"]["q_m"]]}
# 이음매 근처 도로 (y≈5954) 높이 단면: T05 열 0..3, T04 열 1021..1024 (x 4377.07..4380, 4380..4382.93)
r0 = min(rows_route, key=lambda r: abs(y_of_row(r) - 5954.4))
res["seam_profile_y%.1f" % y_of_row(r0)] = {"T04_cols_1020_1024_x_m": [round(3380 + c * TM / 1024, 3) for c in range(1020, 1025)],
                                           "T04_h": [round(float(A[r0, c]), 4) for c in range(1020, 1025)],
                                           "T05_cols_0_4_x_m": [round(4380 + c * TM / 1024, 3) for c in range(0, 5)],
                                           "T05_h": [round(float(B[r0, c]), 4) for c in range(0, 5)]}

# 3) 스폰 방향 변형
def bil(G, fc, fr):
    n = G.shape[0] - 1; c0, r0_ = min(int(fc), n - 1), min(int(fr), n - 1); dc, dr = fc - c0, fr - r0_
    return G[r0_, c0] * (1 - dc) * (1 - dr) + G[r0_, c0 + 1] * dc * (1 - dr) + G[r0_ + 1, c0] * (1 - dc) * dr + G[r0_ + 1, c0 + 1] * dc * dr
sx, sy = 4420.688, 5954.475; obs_idle_z = 28.62853
t = meta["tiles"]["T05_16"]; x0, y0, x1, y1 = t["bounds"]; n = 1024
fc, fr = (sx - x0) / TM * n, (y1 - sy) / TM * n
var = {"row0=N,col0=W (분석기)": bil(B, fc, fr), "row0=S,col0=W": bil(B, fc, n - fr), "row0=N,col0=E": bil(B, n - fc, fr), "row0=S,col0=E": bil(B, n - fc, n - fr)}
res["spawn_orientation_variants"] = {k: {"ground_z": round(float(v), 3), "idle_model_z_minus_ground": round(obs_idle_z - float(v), 4)} for k, v in var.items()}

# 4) 엔진 격자 가설 (1024 점, 간격 1000/1024, 열 k 의 x_local = -499.512 + k*0.9765625; 행 r 의 y_local = +499.512 - r*0.9765625)
HALF = 0.5 * 1023 * (TM / 1024)
def eng_h(G, cx, cy, x, y):
    k = (x - (cx - HALF)) / (TM / 1024); r = ((cy + HALF) - y) / (TM / 1024)
    if k < 0 or k > 1023 or r < 0 or r > 1023:
        return None
    G2 = G[:1024, :1024]; return float(bil(G2, min(k, 1023 - 1e-9), min(r, 1023 - 1e-9)))
def full_h(G, bounds, x, y):
    x0, y0, x1, y1 = bounds; return float(bil(G, (x - x0) / TM * 1024, (y1 - y) / TM * 1024))
res["engine_grid_hypothesis"] = {"half_extent_m": round(HALF, 4), "gap_x_range_at_seam_4380": [round(3880 + HALF, 3), round(4880 - HALF, 3)],
                                 "gap_width_m": round((4880 - HALF) - (3880 + HALF), 4)}
# 경로 선상 (스폰 → 서쪽 300 m, 방위 -2.5652) 에서 full vs engine 차이
hdg = -2.5652; pts = [(sx + s * math.cos(hdg), sy + s * math.sin(hdg)) for s in np.arange(0, 300, 2.0)]
diffs = []
for x, y in pts:
    if x >= 4380:
        G, cx, cy, bd = B, 4880, 5869, meta["tiles"]["T05_16"]["bounds"]
    else:
        G, cx, cy, bd = A, 3880, 5869, meta["tiles"]["T04_16"]["bounds"]
    e = eng_h(G, cx, cy, x, y)
    if e is not None:
        diffs.append(e - full_h(G, bd, x, y))
res["engine_grid_hypothesis"]["route_engine_minus_full_m"] = {"n": len(diffs), "mean": round(float(np.mean(diffs)), 4), "min": round(float(np.min(diffs)), 4), "max": round(float(np.max(diffs)), 4)}
res["engine_grid_hypothesis"]["spawn_engine_minus_full_m"] = round(eng_h(B, 4880, 5869, sx, sy) - full_h(B, meta["tiles"]["T05_16"]["bounds"], sx, sy), 4)
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
