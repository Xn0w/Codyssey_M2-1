"""EKF 정지 속도 표류 대조 (Codex 0430 2절 1·2) — WSL python3 + pyulog. 사용: python3 ekf_drift_dump.py <ulg> <out.json>
정지 미션 finished 기준 [fin−2, disarm+3] 창에서: vehicle_local_position(vx·vy·x·y·reset 카운터·v_xy_valid·xy_valid),
estimator 관련 토픽(존재하는 것만) 요약, 센서(sensor_combined 가속도), GNSS 속도, EKF2/센서 관련 파라미터."""
import json
import math
import sys

from pyulog import ULog

u = ULog(sys.argv[1]); t0 = int(u.start_timestamp)
T = lambda x: (int(x) - t0) / 1e6
P = u.initial_parameters
names = sorted({d.name for d in u.data_list})
def ds(n, multi=0):
    d = [x for x in u.data_list if x.name == n and x.multi_id == multi]; return d[0].data if d else None
mr = ds("mission_result")
ids = []
for k in range(len(mr["timestamp"])):
    i = int(mr["mission_id"][k])
    if i and (not ids or ids[-1] != i): ids.append(i)
stop_id = ids[-1]
fin = next(T(mr["timestamp"][k]) for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == stop_id and int(mr["finished"][k]))
vs = ds("vehicle_status")
dis = next(T(vs["timestamp"][i]) for i in range(1, len(vs["timestamp"])) if int(vs["arming_state"][i]) == 1 and int(vs["arming_state"][i - 1]) == 2 and T(vs["timestamp"][i]) >= fin - 1)
lo, hi = fin - 2.0, dis + 3.0
out = {"ulg": sys.argv[1], "fin": round(fin, 3), "disarm": round(dis, 3), "topics": names,
       "params": {k: P[k] for k in sorted(P) if k.startswith(("EKF2_GPS", "EKF2_HGT", "EKF2_IMU", "EKF2_MAG", "EKF2_AID", "EKF2_EV", "EKF2_OF", "EKF2_GND", "EKF2_DRAG", "EKF2_ZUPT", "EKF2_ABL", "EKF2_ACC", "EKF2_GYR", "EKF2_NOAID", "EKF2_REQ", "EKF2_VEL", "EKF2_POS", "SENS_EN", "RO_", "RA_", "NAV_ACC"))}}
lp = ds("vehicle_local_position")
keys = [k for k in ("x", "y", "vx", "vy", "vz", "xy_reset_counter", "vxy_reset_counter", "v_xy_valid", "xy_valid", "dist_bottom") if k in lp]
rows = [[round(T(lp["timestamp"][i]) - fin, 3)] + [round(float(lp[k][i]), 4) for k in keys] for i in range(len(lp["timestamp"])) if lo <= T(lp["timestamp"][i]) <= hi]
out["lpos_keys"] = ["t_rel"] + keys
out["lpos"] = rows[::2]
if rows:
    ix, iy = keys.index("x") + 1, keys.index("y") + 1
    p0 = next(r for r in rows if r[0] >= 1.0)
    out["lpos_move_after_fin1"] = round(max(math.hypot(r[ix] - p0[ix], r[iy] - p0[iy]) for r in rows if r[0] >= 1.0 and r[0] <= dis - fin), 3)
    iv, iw = keys.index("vx") + 1, keys.index("vy") + 1
    out["v_after_fin1"] = {"max": round(max(math.hypot(r[iv], r[iw]) for r in rows if 1.0 <= r[0] <= dis - fin), 3)}
    out["vel_integral_after_fin1_m"] = round(sum(math.hypot(r[iv], r[iw]) * (b[0] - r[0]) for r, b in zip(rows, rows[1:]) if 1.0 <= r[0] <= dis - fin), 3)
    for c in ("xy_reset_counter", "vxy_reset_counter"):
        if c in keys:
            j = keys.index(c) + 1; out[c + "_values"] = sorted({r[j] for r in rows})
def summ(name, fields, multi=0):
    d = ds(name, multi)
    if d is None:
        return None
    fl = [f for f in fields if f in d]
    sel = [i for i in range(len(d["timestamp"])) if lo <= T(d["timestamp"][i]) <= hi]
    return {"fields": fl, "rows": [[round(T(d["timestamp"][i]) - fin, 3)] + [round(float(d[f][i]), 4) for f in fl] for i in sel][::3]}
out["gps"] = summ("vehicle_gps_position", ["vel_n_m_s", "vel_e_m_s", "vel_m_s", "s_variance_m_s", "fix_type", "eph"]) or summ("sensor_gps", ["vel_n_m_s", "vel_e_m_s", "vel_m_s", "s_variance_m_s", "fix_type", "eph"])
out["accel"] = summ("sensor_combined", ["accelerometer_m_s2[0]", "accelerometer_m_s2[1]", "accelerometer_m_s2[2]"])
out["est_states"] = summ("estimator_states", ["states[4]", "states[5]", "states[13]", "states[14]", "states[15]"])   # vN vE, 가속도 bias xyz (EKF2 상태 순서 — 버전 확인 필요)
out["est_status"] = summ("estimator_status", ["vel_test_ratio", "pos_test_ratio", "hgt_test_ratio", "control_mode_flags", "filter_fault_flags", "solution_status_flags", "reset_count_vel_ne", "reset_count_pos_ne"])
out["est_innov"] = summ("estimator_innovations", ["gps_hvel[0]", "gps_hvel[1]", "gps_hpos[0]", "gps_hpos[1]"])
out["attitude"] = summ("vehicle_attitude", ["q[0]", "q[1]", "q[2]", "q[3]"])
json.dump(out, open(sys.argv[2], "w"))
print("fin", out["fin"], "disarm", out["disarm"], "lpos move after fin+1", out.get("lpos_move_after_fin1"), "v max", out.get("v_after_fin1"), "∫v", out.get("vel_integral_after_fin1_m"),
      "resets", out.get("xy_reset_counter_values"), out.get("vxy_reset_counter_values"), "gps", bool(out["gps"]), "est_states", bool(out["est_states"]), "est_status", bool(out["est_status"]))
