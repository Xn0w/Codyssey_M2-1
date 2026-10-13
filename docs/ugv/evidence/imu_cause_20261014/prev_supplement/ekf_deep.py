"""EKF vs groundtruth deep dump around stop-mission finished. Usage: python3 ekf_deep.py <ulg> <out.json>  (WSL pyulog, read-only)"""
import json, math, sys
from pyulog import ULog

u = ULog(sys.argv[1]); t0 = int(u.start_timestamp); T = lambda x: (int(x) - t0) / 1e6
P = u.initial_parameters

def ds(n, m=0):
    d = [x for x in u.data_list if x.name == n and x.multi_id == m]; return d[0].data if d else None

mr = ds("mission_result"); ids = []
for k in range(len(mr["timestamp"])):
    i = int(mr["mission_id"][k])
    if i and (not ids or ids[-1] != i): ids.append(i)
fin = next(T(mr["timestamp"][k]) for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == ids[-1] and int(mr["finished"][k]))
vs = ds("vehicle_status")
dis = next(T(vs["timestamp"][i]) for i in range(1, len(vs["timestamp"])) if int(vs["arming_state"][i]) == 1 and int(vs["arming_state"][i - 1]) == 2 and T(vs["timestamp"][i]) >= fin - 1)
gt, lp, es, g = ds("vehicle_local_position_groundtruth"), ds("vehicle_local_position"), ds("estimator_states"), ds("estimator_aid_src_gnss_vel")
att, attg, sc, av, st = ds("vehicle_attitude"), ds("vehicle_attitude_groundtruth"), ds("sensor_combined"), ds("vehicle_angular_velocity"), ds("estimator_status")
grav = ds("estimator_aid_src_gravity")
i0 = min(range(len(gt["timestamp"])), key=lambda i: abs(T(gt["timestamp"][i]) - (fin - 1.0)))
ux, uy = float(gt["vx"][i0]), float(gt["vy"][i0]); n = math.hypot(ux, uy); ux, uy = ux / n, uy / n

def idx(d, t):
    return min(range(len(d["timestamp"])), key=lambda j: abs(T(d["timestamp"][j]) - t))

def at(d, kx, ky, t):
    i = idx(d, t); return float(d[kx][i]) * ux + float(d[ky][i]) * uy

def eul(q):
    w, x, y, z = q
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    s = max(-1.0, min(1.0, 2 * (w * y - z * x))); pitch = math.asin(s)
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)

def q_at(d, t):
    i = idx(d, t); return [float(d[f"q[{k}]"][i]) for k in range(4)]

def mean_win(d, key, t, w=0.05):
    vals = [float(d[key][i]) for i in range(len(d["timestamp"])) if t - w <= T(d["timestamp"][i]) <= t + w]
    return sum(vals) / len(vals) if vals else float(d[key][idx(d, t)])

out = {"ulg": sys.argv[1], "fin": round(fin, 3), "disarm": round(dis, 3), "heading_unit": [round(ux, 4), round(uy, 4)],
       "params": {k: v for k, v in P.items() if k.startswith("EKF2_") and any(s in k for s in ("DELAY", "GPS", "ACC", "GYR", "ABL", "GRAV", "IMU", "PREDICT", "NOISE", "GATE"))},
       "cols": ["t_rel", "truth_v", "ekf_v(lpos)", "ekf_v(states)", "gnss_obs", "gnss_innov", "err_lpos", "truth_acc", "pitch_ekf", "pitch_truth", "dpitch", "roll_ekf", "roll_truth",
                "acc_x", "acc_y", "acc_z", "gyro_y", "ab_x", "ab_y", "ab_z", "gb_y", "out_trk_err_v", "grav_fused", "grav_rejected", "grav_innov_x"],
       "rows": []}
ts = [fin + k * 0.05 for k in range(-80, int((dis - fin + 3.0) / 0.05) + 1)]
for t in ts:
    tv = at(gt, "vx", "vy", t); ev = at(lp, "vx", "vy", t); sv = at(es, "states[4]", "states[5]", t)
    gv = at(g, "observation[0]", "observation[1]", t); gi = at(g, "innovation[0]", "innovation[1]", t)
    ta = (at(gt, "vx", "vy", t + 0.1) - at(gt, "vx", "vy", t - 0.1)) / 0.2
    re_, pe, _ = eul(q_at(att, t)); rt, pt, _ = eul(q_at(attg, t))
    ie = idx(es, t)
    ist = idx(st, t)
    row = [round(t - fin, 2), round(tv, 3), round(ev, 3), round(sv, 3), round(gv, 3), round(gi, 3), round(ev - tv, 3), round(ta, 2), round(pe, 2), round(pt, 2), round(pe - pt, 2), round(re_, 2), round(rt, 2),
           round(mean_win(sc, "accelerometer_m_s2[0]", t), 3), round(mean_win(sc, "accelerometer_m_s2[1]", t), 3), round(mean_win(sc, "accelerometer_m_s2[2]", t), 3),
           round(mean_win(av, "xyz[1]", t), 3),
           round(float(es["states[13]"][ie]), 4), round(float(es["states[14]"][ie]), 4), round(float(es["states[15]"][ie]), 4), round(float(es["states[11]"][ie]), 5),
           round(float(st["output_tracking_error[1]"][ist]), 4)]
    if grav:
        ig = idx(grav, t)
        row += [int(grav["fused"][ig]) if "fused" in grav else None, int(grav["innovation_rejected"][ig]) if "innovation_rejected" in grav else None, round(float(grav["innovation[0]"][ig]), 3) if "innovation[0]" in grav else None]
    else:
        row += [None, None, None]
    out["rows"].append(row)
# zero crossings / extrema of EKF velocity after fin (signed along heading)
seq = [(r[0], r[2]) for r in out["rows"] if r[0] >= 0.3]
ext = []
for k in range(1, len(seq) - 1):
    if (seq[k][1] - seq[k - 1][1]) * (seq[k + 1][1] - seq[k][1]) < 0 and abs(seq[k][1]) > 0.05:
        ext.append((seq[k][0], round(seq[k][1], 3)))
zc = [round(seq[k][0], 2) for k in range(1, len(seq)) if seq[k - 1][1] * seq[k][1] < 0]
out["ekf_v_extrema_after_fin"] = ext[:8]; out["ekf_v_zero_cross_after_fin"] = zc[:8]
out["grav_fields"] = [k for k in grav.keys()][:16] if grav else None
out["gps_ts"] = [[round(T(x) - fin, 3)] for x in ds("vehicle_gps_position")["timestamp"] if fin - 0.5 <= T(x) <= fin + 0.5]
gp = ds("vehicle_gps_position")
out["gps_sample_vs_ts"] = [round((int(gp["timestamp"][i]) - int(gp["timestamp_sample"][i])) / 1e6, 4) for i in range(len(gp["timestamp"])) if fin - 0.5 <= T(gp["timestamp"][i]) <= fin + 0.5]
json.dump(out, open(sys.argv[2], "w"))
print("ok fin", round(fin, 3), "dis", round(dis, 3), "rows", len(out["rows"]), "ext", out["ekf_v_extrema_after_fin"], "zc", out["ekf_v_zero_cross_after_fin"])
