"""Fable 원인 분리 (읽기 전용 분석) — tb1_segB_ugv_a 경계 창 raw 재계산.
pose.csv (솎지 않음) 로 차체 z/roll/pitch/yaw/속도, 모델 자세로 네 바퀴 중심·최저점 (서스펜션 변위 미기록 → 공칭 위치 가정),
분석기 격자(1025) 와 엔진 격자 가설(1024, 반폭 499.512) 양쪽에서 바퀴 아래 지면 높이, 틈(4379.512~4380.488) 통과 시각,
IMU·바퀴 관절 속도·명령을 같은 시간축에 연결. 정지 뒤 회복 속도.
사용: python window_analysis.py <tiles_v2> <gzrec_dir> <out_json> <out_table_txt>
"""
import csv, json, math, sys
import numpy as np
from PIL import Image
from pathlib import Path

T = Path(sys.argv[1]); R = Path(sys.argv[2]); OUT = Path(sys.argv[3]); TAB = Path(sys.argv[4])
meta = json.load(open(T / "tiles.json", encoding="utf-8")); ALT = meta["world_origin_alt_m"]; TM = meta["tile_m"]
HALF = 0.5 * 1023 * (TM / 1024); CELL = TM / 1024
GAP = (3880 + HALF, 4880 - HALF)
WHEEL_R, HALF_W = 0.35, 0.125
WHEELS = {"FL": (1.35, 0.8), "FR": (1.35, -0.8), "RL": (-1.35, 0.8), "RR": (-1.35, -0.8)}
_g = {}
def grid(n):
    if n not in _g:
        t = meta["tiles"][n]; img = np.asarray(Image.open(T / n / "heightmap.png"), dtype=np.float64)
        _g[n] = t["zmin"] + img / 65535.0 * t["span"] - ALT
    return _g[n]
def bil(G, fc, fr):
    n = G.shape[0] - 1; c0, r0 = min(max(int(fc), 0), n - 1), min(max(int(fr), 0), n - 1); dc, dr = fc - c0, fr - r0
    return float(G[r0, c0] * (1 - dc) * (1 - dr) + G[r0, c0 + 1] * dc * (1 - dr) + G[r0 + 1, c0] * (1 - dc) * dr + G[r0 + 1, c0 + 1] * dc * dr)
def tile_of(x, y):
    i, j = int(math.floor((x + 620) / TM)), int(math.floor((y + 10631) / TM)); return f"T{i:02d}_{j:02d}"
def h_full(x, y):
    n = tile_of(x, y); x0, y0, x1, y1 = meta["tiles"][n]["bounds"]; return n, bil(grid(n), (x - x0) / TM * 1024, (y1 - y) / TM * 1024)
def h_engine(x, y):
    """엔진 격자 가설: 각 타일 1024 점, 중심 ± 499.512. 틈이면 None."""
    for n in (tile_of(x, y), tile_of(x - 1.0, y), tile_of(x + 1.0, y)):
        if n not in meta["tiles"]:
            continue
        x0, y0, x1, y1 = meta["tiles"][n]["bounds"]; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        k = (x - (cx - HALF)) / CELL; r = ((cy + HALF) - y) / CELL
        if 0 <= k <= 1023 and 0 <= r <= 1023:
            return n, bil(grid(n)[:1024, :1024], min(k, 1023 - 1e-9), min(r, 1023 - 1e-9))
    return None, None
def quat_rot(q, v):
    w, x, y, z = q; vx, vy, vz = v
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty), vy + w * ty + (z * tx - x * tz), vz + w * tz + (x * ty - y * tx))
def rpy(q):
    w, x, y, z = q
    return (math.degrees(math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))), math.degrees(math.asin(max(-1, min(1, 2 * (w * y - z * x))))),
            math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))))

rows = []
for r in csv.DictReader(open(R / "pose.csv")):
    rows.append((float(r["stamp"]), float(r["x"]), float(r["y"]), float(r["z"]), (float(r["qw"]), float(r["qx"]), float(r["qy"]), float(r["qz"]))))
res = {"pose_rows": len(rows), "pose_dt_median_s": round(float(np.median(np.diff([r[0] for r in rows]))), 4),
       "gap_hypothesis_x": [round(GAP[0], 3), round(GAP[1], 3)]}

def sample(rw):
    t, x, y, z, q = rw; roll, pitch, yaw = rpy(q)
    o = {"t": t, "x": x, "y": y, "z": z, "roll": roll, "pitch": pitch, "yaw": yaw}
    n, g = h_full(x, y); o["tile"] = n; o["dz_full"] = z - g
    ne, ge = h_engine(x, y); o["dz_engine"] = None if ge is None else z - ge
    ay = quat_rot(q, (0, 1, 0))                      # 바퀴 축 (차체 y) 월드 방향
    horiz = math.sqrt(max(1 - ay[2] ** 2, 0))        # 최저점은 축에 수직인 평면에서 아래로 R*horiz
    for w, (lx, ly) in WHEELS.items():
        c = quat_rot(q, (lx, ly, WHEEL_R)); cx, cy, cz = x + c[0], y + c[1], z + c[2]
        bz = cz - WHEEL_R * horiz
        nf, gf = h_full(cx, cy); ne, ge = h_engine(cx, cy)
        o[w] = {"cx": cx, "cy": cy, "cz": cz, "bottom_z": bz, "g_full": gf, "bottom_minus_g_full": bz - gf,
                "g_engine": ge, "bottom_minus_g_engine": None if ge is None else bz - ge, "in_gap": GAP[0] < cx < GAP[1]}
    return o

# 속도
def speed(i):
    if i == 0: return 0.0
    t0, x0, y0 = rows[i - 1][0], rows[i - 1][1], rows[i - 1][2]; t1, x1, y1 = rows[i][0], rows[i][1], rows[i][2]
    return math.dist((x0, y0), (x1, y1)) / max(t1 - t0, 1e-6)

# 1) 전 구간 요약: 이음매 전(T05_16 주행), 후(T04_16 주행), 정지
S = [sample(r) for r in rows[::5]]
pre = [o for o in S if o["tile"] == "T05_16" and o["t"] > 70 and o["x"] > 4384]
post = [o for o in S if o["tile"] == "T04_16" and o["x"] < 4376]
res["pre_seam_T05_16"] = {"n": len(pre), "dz_full_mean": round(float(np.mean([o["dz_full"] for o in pre])), 4), "dz_full_min": round(min(o["dz_full"] for o in pre), 4),
                          "dz_full_max": round(max(o["dz_full"] for o in pre), 4), "roll_mean": round(float(np.mean([o["roll"] for o in pre])), 2),
                          "roll_absmax": round(max(abs(o["roll"]) for o in pre), 2), "pitch_absmax": round(max(abs(o["pitch"]) for o in pre), 2),
                          "dz_engine_mean": round(float(np.mean([o["dz_engine"] for o in pre if o["dz_engine"] is not None])), 4)}
res["post_seam_T04_16"] = {"n": len(post), "dz_full_mean": round(float(np.mean([o["dz_full"] for o in post])), 4), "dz_full_min": round(min(o["dz_full"] for o in post), 4),
                           "dz_full_max": round(max(o["dz_full"] for o in post), 4), "roll_min": round(min(o["roll"] for o in post), 2), "roll_max": round(max(o["roll"] for o in post), 2),
                           "pitch_absmax": round(max(abs(o["pitch"]) for o in post), 2)}
# 바퀴별 최저점 − 지면 (서스펜션 공칭 가정) 이음매 전/후 평균
for tag, grp in (("pre", pre), ("post", post)):
    res[f"wheel_bottom_minus_ground_full_{tag}"] = {w: round(float(np.mean([o[w]["bottom_minus_g_full"] for o in grp])), 4) for w in WHEELS}

# 2) 경계 창 raw
W0, W1 = 81.3, 83.6
win_idx = [i for i, r in enumerate(rows) if W0 <= r[0] <= W1]
win = []
for i in win_idx:
    o = sample(rows[i]); o["v"] = speed(i); win.append(o)
res["window"] = {"t0": W0, "t1": W1, "n_raw": len(win), "v_mean": round(float(np.mean([o["v"] for o in win])), 3)}
# 바퀴 중심 x 가 틈 구간에 드는 시각 (서진 — x 감소)
ev = {}
for w in WHEELS:
    xs = [(o["t"], o[w]["cx"]) for o in win]
    enter = next((t for t, cx in xs if cx < GAP[1]), None); leave = next((t for t, cx in xs if cx < GAP[0]), None)
    # 지지 상실 가설: 바퀴 최저점 (≈중심 x) 이 T05 엔진 가장자리 (4380.488) 서쪽으로 → T04 가장자리 (4379.512) 서쪽까지
    ev[w] = {"center_enters_gap_t": enter, "center_leaves_gap_t": leave, "unsupported_s": None if (enter is None or leave is None) else round(leave - enter, 3)}
res["wheel_gap_events"] = ev
# 자세 이상 시작: 창 안에서 |roll| > 0.5°, z 가 창 시작 dz_full 평균보다 0.02 이상 하강
roll0 = float(np.mean([o["roll"] for o in win[:10]])); dz0 = float(np.mean([o["dz_full"] for o in win[:10]]))
res["onset"] = {"roll_ref": round(roll0, 3), "dz_ref": round(dz0, 4),
                "t_roll_dev_gt_0_5deg": next((o["t"] for o in win if abs(o["roll"] - roll0) > 0.5), None),
                "t_roll_dev_gt_2deg": next((o["t"] for o in win if abs(o["roll"] - roll0) > 2.0), None),
                "t_dz_drop_gt_0_02": next((o["t"] for o in win if o["dz_full"] - dz0 < -0.02), None),
                "t_dz_drop_gt_0_10": next((o["t"] for o in win if o["dz_full"] - dz0 < -0.10), None),
                "t_pitch_dev_gt_1deg": next((o["t"] for o in win if abs(o["pitch"] - float(np.mean([p["pitch"] for p in win[:10]]))) > 1.0), None),
                "roll_min_in_window": (min(win, key=lambda o: o["roll"])["t"], round(min(o["roll"] for o in win), 2)),
                "roll_max_in_window": (max(win, key=lambda o: o["roll"])["t"], round(max(o["roll"] for o in win), 2)),
                "pitch_min_in_window": (min(win, key=lambda o: o["pitch"])["t"], round(min(o["pitch"] for o in win), 2)),
                "pitch_max_in_window": (max(win, key=lambda o: o["pitch"])["t"], round(max(o["pitch"] for o in win), 2)),
                "dz_min_in_window": (min(win, key=lambda o: o["dz_full"])["t"], round(min(o["dz_full"] for o in win), 4))}

# 3) IMU 창
imu = []
for r in csv.DictReader(open(R / "imu.csv")):
    t = float(r["stamp"])
    if W0 <= t <= W1:
        imu.append((t, float(r["ax"]), float(r["ay"]), float(r["az"]), float(r["gx"]), float(r["gy"]), float(r["gz"])))
if imu:
    A = np.array(imu)
    def ext(col, name):
        i0, i1 = int(np.argmin(A[:, col])), int(np.argmax(A[:, col]))
        return {f"{name}_min": (round(A[i0, 0], 3), round(A[i0, col], 3)), f"{name}_max": (round(A[i1, 0], 3), round(A[i1, col], 3))}
    res["imu_window"] = {"n": len(imu), **ext(3, "az"), **ext(1, "ax"), **ext(2, "ay"), **ext(4, "gx"), **ext(5, "gy")}
    # 0.05 s 구간별 az 평균 (체공/충격 구간 식별)
    bins = {}
    for t, ax, ay, az, gx, gy, gz in imu:
        b = round(math.floor(t / 0.05) * 0.05, 2); bins.setdefault(b, []).append((az, gx))
    res["imu_az_gx_per_50ms"] = {str(b): (round(float(np.mean([v[0] for v in vs])), 2), round(float(np.mean([v[1] for v in vs])), 3)) for b, vs in sorted(bins.items())}

# 4) 관절 창 (바퀴별 속도, 0.1 s 평균) + 명령
jb = {}
for r in csv.DictReader(open(R / "joint.csv")):
    t = float(r["stamp"])
    if W0 - 0.3 <= t <= W1 + 0.3:
        b = round(math.floor(t / 0.1) * 0.1, 1); jb.setdefault(b, {}).setdefault(r["name"], []).append(float(r["vel"]))
res["joint_vel_per_100ms"] = {str(b): {k[:-6].replace("wheel_", ""): round(float(np.mean(v)), 2) for k, v in sorted(d.items())} for b, d in sorted(jb.items())}
cmd = [(float(r["stamp"]), float(r["v0"])) for r in csv.DictReader(open(R / "cmd.csv"))]
cw = [(t, v) for t, v in cmd if W0 - 0.3 <= t <= W1 + 0.3]
res["cmd_window"] = {"n": len(cw), "v0_min": round(min(v for _, v in cw), 2) if cw else None, "v0_max": round(max(v for _, v in cw), 2) if cw else None,
                     "note": "cmd stamp 가 0 이면 헤더 미설정 — 시간 연결 불가"}
res["cmd_stamp_zero_fraction"] = round(sum(1 for t, _ in cmd if t == 0) / max(len(cmd), 1), 3)

# 5) 정지 뒤 회복
allS = [dict(sample(rows[i]), v=speed(i)) for i in range(0, len(rows), 10)]
rest = [o for o in allS if o["v"] < 0.05 and o["t"] > 100]
if rest:
    t0 = rest[0]["t"]
    pick = lambda dt: min(rest, key=lambda o: abs(o["t"] - (t0 + dt)))
    res["rest_recovery"] = {"rest_start_t": round(t0, 2), "samples": [{"t+": dt, "t": round(pick(dt)["t"], 2), "dz_full": round(pick(dt)["dz_full"], 4), "roll": round(pick(dt)["roll"], 2),
                                                                         "pitch": round(pick(dt)["pitch"], 2)} for dt in (0, 10, 30, 60, 90) if pick(dt)["t"] <= rest[-1]["t"] + 1]}
    a, b = pick(0), pick(min(60, rest[-1]["t"] - t0))
    res["rest_recovery"]["dz_rate_mm_per_s"] = round((b["dz_full"] - a["dz_full"]) / max(b["t"] - a["t"], 1e-6) * 1000, 3)
    res["rest_recovery"]["roll_rate_deg_per_s"] = round((b["roll"] - a["roll"]) / max(b["t"] - a["t"], 1e-6), 4)
    res["rest_recovery"]["rest_end_t"] = round(rest[-1]["t"], 2)
    res["rest_recovery"]["rest_wheel_bottom_minus_g_full_start"] = {w: round(a[w]["bottom_minus_g_full"], 4) for w in WHEELS}
    res["rest_recovery"]["rest_wheel_bottom_minus_g_full_end"] = {w: round(b[w]["bottom_minus_g_full"], 4) for w in WHEELS}

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
# 표: 창 안 raw 전부 (약 56 Hz)
with open(TAB, "w", encoding="utf-8") as f:
    f.write("t\tx\ty\tz\tv\troll\tpitch\tdz_full\tdz_eng\t" + "\t".join(f"{w}_cx\t{w}_gap\t{w}_bot-g_full\t{w}_bot-g_eng" for w in WHEELS) + "\n")
    for o in win:
        f.write(f"{o['t']:.3f}\t{o['x']:.3f}\t{o['y']:.3f}\t{o['z']:.4f}\t{o['v']:.2f}\t{o['roll']:.2f}\t{o['pitch']:.2f}\t{o['dz_full']:.4f}\t"
                f"{'' if o['dz_engine'] is None else f'{o[chr(100)+chr(122)+chr(95)+chr(101)+chr(110)+chr(103)+chr(105)+chr(110)+chr(101)]:.4f}'}\t"
                + "\t".join(f"{o[w]['cx']:.3f}\t{int(o[w]['in_gap'])}\t{o[w]['bottom_minus_g_full']:.4f}\t{'' if o[w]['bottom_minus_g_engine'] is None else f'{o[w][chr(98)+chr(111)+chr(116)+chr(116)+chr(111)+chr(109)+chr(95)+chr(109)+chr(105)+chr(110)+chr(117)+chr(115)+chr(95)+chr(103)+chr(95)+chr(101)+chr(110)+chr(103)+chr(105)+chr(110)+chr(101)]:.4f}'}" for w in WHEELS) + "\n")
print(json.dumps({k: v for k, v in res.items() if k not in ("imu_az_gx_per_50ms", "joint_vel_per_100ms")}, ensure_ascii=False, indent=1))
