"""Fable 검토 2 — (1) FR 두 점 합의 마찰 상자 검사 (fdir 기저: 축=월드x, 전방=월드y 를 법선에 수직 투영), (2) 접촉 상실·재접촉 주기와 깊이 회복 속도, (3) 차체·바퀴 링크 y 드리프트, (4) 이음매 양 타일 가장자리 행의 y 경사 → 원통 최저점 변위."""
import json, csv, math, sys, numpy as np
from PIL import Image
from pathlib import Path
R = Path("seamB4/runs"); out = {}
def basis(n, first):
    t = np.cross(n, first); t /= np.linalg.norm(t); ax = n / np.linalg.norm(n)
    c0 = t * math.cos(math.pi/2) + np.cross(ax, t) * math.sin(math.pi/2) + ax * np.dot(ax, t) * (1 - math.cos(math.pi/2)); return c0, t
for tag in ("b4e_exact", "b4d_N", "b4d_S"):
    rows = [json.loads(l) for l in open(R / f"{tag}_raw.jsonl", encoding="utf-8")]; t0 = rows[0]["sim_t"]
    res = {}
    for w in ("wheel_front_right", "wheel_front_left", "wheel_rear_left"):
        sum_ax, sum_fw, pt_ax, pt_fw, n2 = [], [], [], [], 0
        for r in rows:
            if r["sim_t"] - t0 < 2: continue
            m = r["wheels"].get(w)
            if not m or not m["pts"]: continue
            F = np.zeros(3); fn_sum = 0.0; nbar = np.zeros(3)
            for p in m["pts"]:
                n = np.array(p["n"]); f = np.array(p["f1"]); fn = f @ n; nbar += n; F += f; fn_sum += fn
                if fn > 1:
                    d0, d1 = basis(n, np.array([0, 1.0, 0])); pt_fw.append(abs(f @ d0) / fn); pt_ax.append(abs(f @ d1) / fn)
            if len(m["pts"]) == 2: n2 += 1
            if fn_sum > 1:
                d0, d1 = basis(nbar / np.linalg.norm(nbar), np.array([0, 1.0, 0])); sum_fw.append(abs(F @ d0) / fn_sum); sum_ax.append(abs(F @ d1) / fn_sum)
        res[w[6:]] = {"samples_2pts": n2, "point_axle_lambda_over_fn_max": round(max(pt_ax), 4), "point_fwd_lambda_over_fn_max": round(max(pt_fw), 4),
                      "SUM_axle_lambda_over_fn_max": round(max(sum_ax), 4), "SUM_fwd_lambda_over_fn_max": round(max(sum_fw), 4),
                      "SUM_axle_gt_1.005": sum(1 for v in sum_ax if v > 1.005), "point_axle_gt_1.005": sum(1 for v in pt_ax if v > 1.005)}
    out[tag] = res
print(json.dumps(out, indent=1))
# (2) 주기: FR depth 시계열에서 점프 (>2 mm 증가) 시각, 사이 기울기
rows = [json.loads(l) for l in open(R / "b4e_exact_raw.jsonl", encoding="utf-8")]
ts, ds, dys = [], [], []
for r in rows:
    m = r["wheels"].get("wheel_front_right")
    if m and m["pts"]: ts.append(r["sim_t"]); ds.append(min(p["d"] for p in m["pts"]) * 1000); dys.append(min(p["pos"][1] for p in m["pts"]) + 4631)
jumps = [(round(ts[i], 3), round(ds[i-1], 2), round(ds[i], 2), round(dys[i-1]*1000, 3), round(dys[i]*1000, 3)) for i in range(1, len(ts)) if ds[i] - ds[i-1] > 2]
slopes = []
for a, b in zip(jumps, jumps[1:]):
    ia = ts.index(a[0]) + 2; ib = ts.index(b[0]) - 2
    if ib - ia > 5:
        p = np.polyfit(ts[ia:ib], ds[ia:ib], 1); q = np.polyfit(ts[ia:ib], [d*1000 for d in dys[ia:ib]], 1); slopes.append((round(p[0], 3), round(q[0], 4)))
print("FR depth jumps (t, d_before, d_after, dy_before_mm, dy_after_mm):", jumps)
print("periods s:", [round(b[0]-a[0], 2) for a, b in zip(jumps, jumps[1:])])
print("between-jump slopes (depth mm/s, dy mm/s):", slopes)
# CSV: FR c_age>0.002 rows, link y drift
for tag in ("b4e_exact", "b4d_N"):
    cr = list(csv.DictReader(open(R / f"{tag}.csv")))
    ages = [(float(r["sim_t"]), float(r["wheel_front_right_c_age"])) for r in cr if r["wheel_front_right_c_age"] not in ("", "nan") and float(r["wheel_front_right_c_age"]) > 0.0025]
    keys = [k for k in cr[0].keys() if "link_y" in k or k in ("y",)]
    t = np.array([float(r["sim_t"]) for r in cr]); sel = t > t[0] + 2
    drift = {k: round(float(np.polyfit(t[sel], np.array([float(r[k]) for r in cr])[sel], 1)[0]) * 1000, 4) for k in keys}
    print(tag, "FR c_age>2.5ms rows:", ages[:12], "count", len(ages)); print(tag, "y drift mm/s (fit after 2 s):", drift)
    print(tag, "roll/pitch last:", cr[-1]["roll"], cr[-1]["pitch"], " FR link y first/last:", cr[5]["wheel_front_right_link_y"], cr[-1]["wheel_front_right_link_y"])
# (4) 가장자리 행 경사 (PNG, tiles_v2 와 동일)
T = Path("../../stage5/tiles_v2"); meta = json.load(open(T / "tiles.json", encoding="utf-8"))
def grid(n): t = meta["tiles"][n]; return t["zmin"] + np.asarray(Image.open(T / n / "heightmap.png"), float) / 65535 * t["span"] - 172.1
A, B = grid("T16_05"), grid("T16_06"); cell = 1000/1024
for xw in (15400.0, 15401.6):
    c = (xw - 15380) / cell; c0 = int(c); fc = c - c0
    def rowv(G, r): return G[r, c0] * (1-fc) + G[r, c0+1] * fc
    hB0, hB1 = rowv(B, 1024), rowv(B, 1023)      # T16_06 남쪽 끝 행(1024)=y −4631, 그 다음 행(1023)=y −4630.02
    hA0, hA1 = rowv(A, 0), rowv(A, 1)             # T16_05 북쪽 끝 행(0)=y −4631, 행 1 = y −4631.98
    sB = (hB1 - hB0) / cell; sA = (hA0 - hA1) / cell   # dz/dy (북쪽으로)
    print(f"x={xw}: T16_06 edge h={hB0:.4f} slope_dz/dy={sB:+.5f} (lowest-point shift along y = {-0.35*sB*1000:+.2f} mm) | T16_05 edge h={hA0:.4f} slope_dz/dy={sA:+.5f} (shift {-0.35*sA*1000:+.2f} mm) | edge height diff T06-T05 = {(hB0-hA0)*1000:+.2f} mm")
