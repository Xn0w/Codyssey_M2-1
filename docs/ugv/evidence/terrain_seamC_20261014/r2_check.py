"""R2 저속 통과 판정 (WSL python3, 사전 기준 SEAMC_R2_criteria.md). 사용: python3 r2_check.py <tiles_v2> <out_dir> <TAG>
구간 (구동 기록 drive.csv 의 sim 시각): settle (첫 sim+2 s ~ 구동 시작), drive (구동 시작 ~ 끝), hold (구동 끝 + 3 s ~ 기록 끝)."""
import csv, json, math, sys
import numpy as np
from PIL import Image
from pathlib import Path
T = Path(sys.argv[1]); O = Path(sys.argv[2]); tag = sys.argv[3]
meta = json.load(open(T / "tiles.json")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]; ALT = meta["world_origin_alt_m"]; _img = {}
def z_at(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); name = f"T{i:02d}_{j:02d}"; t = meta["tiles"][name]
    if name not in _img: _img[name] = np.asarray(Image.open(T / name / "heightmap.png"), dtype=np.float64)
    img = _img[name]; x0, y0, x1, y1 = t["bounds"]; n = img.shape[0] - 1
    fc, fr = (x - x0) / (x1 - x0) * n, (y1 - y) / (y1 - y0) * n; c0, r0 = min(int(fc), n - 1), min(int(fr), n - 1); dc, dr = fc - c0, fr - r0
    v = img[r0, c0] * (1 - dc) * (1 - dr) + img[r0, c0 + 1] * dc * (1 - dr) + img[r0 + 1, c0] * (1 - dc) * dr + img[r0 + 1, c0 + 1] * dc * dr
    return name, t["zmin"] + v / 65535.0 * t["span"] - ALT
W = ["wheel_front_left", "wheel_front_right", "wheel_rear_left", "wheel_rear_right"]; SUSP = ["susp_front_left", "susp_front_right", "susp_rear_left", "susp_rear_right"]
def f(r, k):
    try: return float(r[k])
    except (ValueError, KeyError, TypeError): return None
rec = {"tag": tag, "markers": [m for m in ("contaminated", "invalid", "invalid_evidence", "invalid_stop", "abort") if (O / f"{tag}.{m}").exists()]}
gl = (O / f"{tag}_gz_detail.log").read_text().strip().splitlines(); rec["gz_detail_rc"] = int(gl[-1].split("=")[1]) if gl and gl[-1].startswith("gz_detail_rc") else None
rec["aabb"] = json.load(open(O / f"aabb_{tag}.json"))
D = [r for r in csv.DictReader(open(O / f"{tag}_drive.csv")) if r["sim"] not in ("", "None")]
ds = [float(r["sim"]) for r in D if r["phase"] == "drive"]; t_d0, t_d1 = (min(ds), max(ds)) if ds else (None, None)
rec["drive_window"] = [t_d0, t_d1]; rec["cmd_rad_s"] = sorted({float(r["cmd_rad_s"]) for r in D if r["phase"] == "drive"})
R = list(csv.DictReader(open(O / f"{tag}.csv"))); t0 = float(R[0]["sim_t"])
def win(a, b): return [r for r in R if a <= float(r["sim_t"]) <= b]
settle = win(t0 + 2.0, t_d0) if t_d0 else []; drive = win(t_d0, t_d1) if t_d0 else []; hold = win(t_d1 + 3.0, 1e9) if t_d1 else []
act = win(t_d0 + 3.0, t_d1 - 3.0) if t_d0 else []          # 가속·감속 2 s 램프 + 1 s 여유 제외
c = {}
c["recorder_ok_no_markers"] = rec["gz_detail_rc"] == 0 and not rec["markers"]
c["aabb_candidate_2_158"] = rec["aabb"] == {"aabb_500": 2, "aabb_499_512": 158}
rec["cmd_rad_s"] = [min(rec["cmd_rad_s"]), max(rec["cmd_rad_s"])] if rec["cmd_rad_s"] else None
c["drive_phase_recorded"] = bool(ds) and abs(rec["cmd_rad_s"][1] - round(1 / 0.35, 4)) < 1e-6 and 14.0 <= (t_d1 - t_d0) <= 16.0
if len(act) > 5:
    p0, p1 = act[0], act[-1]; dt = float(p1["sim_t"]) - float(p0["sim_t"]); dx, dy = f(p1, "x") - f(p0, "x"), f(p1, "y") - f(p0, "y")
    vmean = math.hypot(dx, dy) / dt; hd = math.atan2(dy, dx); yaw = f(p0, "yaw"); dh = abs((hd - yaw + math.pi) % (2 * math.pi) - math.pi)
    rec["actual"] = {"v_mean_mps": round(vmean, 3), "heading_err_deg": round(math.degrees(dh), 2), "dt": round(dt, 2)}
    c["speed_0.8_1.2_and_forward"] = 0.8 <= vmean <= 1.2 and math.degrees(dh) <= 10.0
else:
    c["speed_0.8_1.2_and_forward"] = None
cross = {}
for w in W:
    xs = [f(r, f"{w}_link_x") for r in R if f(r, f"{w}_link_x") is not None]
    cross[w] = {"x_first": round(xs[0], 3) if xs else None, "x_last": round(xs[-1], 3) if xs else None,
                "other_seq": [o for i, o in enumerate([r[f"{w}_other"] for r in R if r[f"{w}_other"]]) if i == 0 or o != [r[f"{w}_other"] for r in R if r[f"{w}_other"]][i - 1]][:6]}
rec["crossing"] = cross
c["all_wheels_crossed"] = all(v["x_first"] is not None and v["x_first"] > 4380.6 and v["x_last"] < 4379.4 for v in cross.values())
mw = drive + hold
st = {w: [r[f"{w}_c_state"] for r in mw] for w in W}
rec["valid_ratio_drive_hold"] = {w: round(s_.count("VALID") / max(1, len(s_)), 4) for w, s_ in st.items()}
c["contact_valid_95"] = all(v >= 0.95 for v in rec["valid_ratio_drive_hold"].values())
rp = [(abs(math.degrees(f(r, "roll"))), abs(math.degrees(f(r, "pitch")))) for r in settle + mw]
rec["roll_abs_max_deg"] = round(max(a for a, _ in rp), 3) if rp else None; rec["pitch_abs_max_deg"] = round(max(b for _, b in rp), 3) if rp else None
c["attitude_le_2deg"] = bool(rp) and rec["roll_abs_max_deg"] <= 2.0 and rec["pitch_abs_max_deg"] <= 2.0
hz = {}
for w in W:
    v = [f(r, f"{w}_z") - z_at(f(r, f"{w}_link_x"), f(r, f"{w}_link_y"))[1] for r in settle + mw if None not in (f(r, f"{w}_z"), f(r, f"{w}_link_x"), f(r, f"{w}_link_y"))]
    hz[w] = [round(min(v), 4), round(max(v), 4)] if v else None
rec["wheel_height"] = hz
c["wheel_height_0.29_0.41"] = all(v and 0.29 <= v[0] and v[1] <= 0.41 for v in hz.values())
q = {s_: [f(r, f"{s_}_q") for r in settle + mw if f(r, f"{s_}_q") is not None] for s_ in SUSP}
rec["susp_q_range"] = {s_: [round(min(v), 5), round(max(v), 5)] if v else None for s_, v in q.items()}
c["susp_within_limit"] = all(v and max(abs(v[0]), abs(v[1])) < 0.098 for v in rec["susp_q_range"].values())
bz = lambda rows: [f(r, "z") - z_at(f(r, "x"), f(r, "y"))[1] for r in rows]
b_s, b_h = bz(settle), bz(hold)
rec["base_dz"] = {"settle_median": round(float(np.median(b_s)), 4) if b_s else None, "hold_median": round(float(np.median(b_h)), 4) if b_h else None}
c["no_persistent_sinking_0.03"] = bool(b_s and b_h) and abs(np.median(b_h) - np.median(b_s)) <= 0.03
sp = []
for r0, r1 in zip(hold, hold[1:]):
    dt = float(r1["sim_t"]) - float(r0["sim_t"])
    if dt > 0: sp.append(math.hypot(f(r1, "x") - f(r0, "x"), f(r1, "y") - f(r0, "y")) / dt)
rec["hold_speed_max"] = round(max(sp), 4) if sp else None
c["stopped_hold_lt_0.05"] = bool(sp) and float(np.median(sp)) < 0.05
rec["checks"] = c
rec["status"] = "FAIL" if any(v is False for v in c.values()) else ("UNCONFIRMED" if any(v is None for v in c.values()) else "PASS")
json.dump(rec, open(O / f"r2check_{tag}.json", "w"), ensure_ascii=False, indent=1)
print(tag, rec["status"], json.dumps({k: rec.get(k) for k in ("checks", "actual", "roll_abs_max_deg", "pitch_abs_max_deg", "base_dz", "hold_speed_max", "valid_ratio_drive_hold")}, ensure_ascii=False))
for w, v in cross.items(): print(" ", w, v, hz[w])
