import csv, json, sys
import numpy as np
from pyulog import ULog
ulg, gd, fin, outp = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
u = ULog(ulg); d = lambda n: [x for x in u.data_list if x.name == n and x.multi_id == 0][0].data
am = d("actuator_motors"); at = np.array(am["timestamp"], float) * 1e-6; c0 = np.array(am["control[0]"], float)
rs = d("rover_speed_setpoint"); rt = np.array(rs["timestamp"], float) * 1e-6
lo, hi = fin - 2.5, fin - 0.05
J = {}
for r in csv.DictReader(open(gd + "/joint.csv")):
    t = float(r["stamp"])
    if lo - 0.1 <= t <= hi + 0.1 and "wheel" in r["name"] and "steer" not in r["name"]: J.setdefault(r["name"], []).append((t, float(r["vel"])))
n0 = sorted(J)[0]; JT = np.array([x[0] for x in J[n0]]); JV = np.mean([np.array([x[1] for x in J[n]])[:len(JT)] for n in sorted(J)], axis=0) * 0.35
dv = np.diff(JV); jt = JT[1:]
thr = 4 * np.median(np.abs(dv)); imp = np.where(np.abs(dv) > thr)[0]
sel = (at >= lo) & (at <= hi); ats = at[sel]; cs = c0[sel]
# for each actuator_motors message, time to the next joint impulse
lat = []
for t in ats:
    k = np.searchsorted(jt[imp], t)
    if k < len(imp): lat.append(round((jt[imp][k] - t) * 1000, 2))
latv, latc = np.unique(np.round(lat, 1), return_counts=True)
dc = np.diff(cs)
out = {"actuator_motors": {"n_W1": int(sel.sum()), "dt_med_ms": round(float(np.median(np.diff(ats))) * 1000, 2), "ts_mod_4000us": {str(int(k)): int(v) for k, v in zip(*np.unique((np.round(ats * 1e6) % 4000).astype(int), return_counts=True))},
                           "control0_first12": [round(float(x), 4) for x in cs[:12]], "dcontrol0_first12": [round(float(x), 4) for x in dc[:12]],
                           "dcontrol0_sign_alternation_frac": round(float(np.mean(np.sign(dc[1:]) != np.sign(dc[:-1]))), 3), "dcontrol0_mean_pos": round(float(np.mean(dc[dc > 0])), 4) if np.any(dc > 0) else None, "dcontrol0_mean_neg": round(float(np.mean(dc[dc < 0])), 4) if np.any(dc < 0) else None},
       "rover_speed_setpoint_dt_med_ms": round(float(np.median(np.diff(rt[(rt >= lo) & (rt <= hi)]))) * 1000, 2),
       "joint_impulses": {"n": int(len(imp)), "gap_ms_hist": {str(int(round(g * 1000))): int(c) for g, c in zip(*np.unique(np.round(np.diff(jt[imp]), 3), return_counts=True))},
                          "dv_first12_mps": [round(float(dv[i]), 4) for i in imp[:12]], "dv_sign_alternation_frac": round(float(np.mean(np.sign(dv[imp][1:]) != np.sign(dv[imp][:-1]))), 3)},
       "latency_actuator_msg_to_next_joint_impulse_ms_hist": {str(k): int(v) for k, v in zip(latv, latc)}}
# correlate command step and joint dv: pair each impulse with the nearest preceding actuator message
pairs = []
for i in imp:
    k = np.searchsorted(ats, jt[i]) - 1
    if 0 <= k < len(dc): pairs.append((float(dc[k]) if k < len(dc) else np.nan, float(dv[i])))
if pairs:
    P = np.array(pairs); P = P[~np.isnan(P[:, 0])]
    out["corr_dcontrol_vs_joint_dv"] = round(float(np.corrcoef(P[:, 0], P[:, 1])[0, 1]), 3); out["ratio_joint_dv_per_dcontrol"] = round(float(np.sum(P[:, 0] * P[:, 1]) / np.sum(P[:, 0] ** 2)), 3)
json.dump(out, open(outp, "w"), indent=1); print(json.dumps(out))
