"""IMU 과대 감속 원인 분리 — ULog 단계별 대조 (WSL python3 + pyulog, 읽기 전용).
사용: python3 imu_cause.py <ulg> <out.json> <label> [mode]   mode = acc3 (기본: 끝 경계 정지 회차) | off (RA −1, finished 뒤 크롤 — 제동 창 = 선행 도달~finished)

고정 창 (결과 전 정의, fin = 정지 미션 mission_result.finished 첫 시각, dis = disarm):
  W0 cruise     [fin−5.0, fin−3.0]   (acc3; 등속 기준 — truth 가속 평균 |a| ≤ 0.6 이어야 유효)
  W1 brake      [fin−2.5, fin−0.05]  (acc3 공통 창)   / off: [선행 도달, fin−0.05]
  W1f fullbrake [t_dec, fin−0.05]    t_dec = fin 앞에서 truth 가속 > −0.4 였던 마지막 시각
  W2 stop_armed [fin+0.8, dis−0.1]   (정적 기준)
  W3 disarmed   [dis+0.3, dis+2.5]   (정적 기준, EKF 동결 가능)
지표: 단계별 (sensor_accel 원시 × dt, vehicle_imu delta_velocity 합, sensor_combined accel × integral_dt) 를 truth 자세(전체 쿼터니언)로 NED 회전 + 중력(0,0,+9.8) 보정 뒤
      진행 방향(정지 전 1 s truth 속도 단위벡터) 투영 Δv 와 truth Δv 비교. 표본 수·dt·누락, 원시 평균/분산/두봉우리 비율/스펙트럼, clipping,
      EKF−truth(출력·융합지평), GNSS 관측·혁신·융합/기각 수, Δpitch(EKF−truth), 정지 뒤 EKF 극값·영점.
"""
import hashlib, json, math, sys
from pyulog import ULog

ulg, outp, label = sys.argv[1], sys.argv[2], sys.argv[3]
mode = sys.argv[4] if len(sys.argv) > 4 else "acc3"
G = 9.8
u = ULog(ulg); t0 = int(u.start_timestamp); T = lambda x: (int(x) - t0) / 1e6
P = u.initial_parameters

def ds(n, m=0):
    d = [x for x in u.data_list if x.name == n and x.multi_id == m]; return d[0].data if d else None

def idx(d, t):
    ts = d["timestamp"]; lo, hi = 0, len(ts) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if T(ts[mid]) < t: lo = mid + 1
        else: hi = mid
    if lo > 0 and abs(T(ts[lo - 1]) - t) < abs(T(ts[lo]) - t): lo -= 1
    return lo

def q_rot(q, v):  # rotate body vector v by quaternion q (w,x,y,z) -> frame
    w, x, y, z = q; vx, vy, vz = v
    # q v q*
    t2 = w * x; t3 = w * y; t4 = w * z; t5 = -x * x; t6 = x * y; t7 = x * z; t8 = -y * y; t9 = y * z; t10 = -z * z
    return (2 * ((t8 + t10) * vx + (t6 - t4) * vy + (t3 + t7) * vz) + vx,
            2 * ((t4 + t6) * vx + (t5 + t10) * vy + (t9 - t2) * vz) + vy,
            2 * ((t7 - t3) * vx + (t2 + t9) * vy + (t5 + t8) * vz) + vz)

def eul(q):
    w, x, y, z = q
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    pitch = math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x))))
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return math.degrees(roll), math.degrees(pitch), math.degrees(yaw)

mr = ds("mission_result"); ids = []
for k in range(len(mr["timestamp"])):
    i = int(mr["mission_id"][k])
    if i and (not ids or ids[-1] != i): ids.append(i)
sid = ids[-1]
t_mis = next(T(mr["timestamp"][k]) for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == sid)
fin = next((T(mr["timestamp"][k]) for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == sid and int(mr["finished"][k])), None)
vs = ds("vehicle_status")
dis = next((T(vs["timestamp"][i]) for i in range(1, len(vs["timestamp"])) if int(vs["arming_state"][i]) == 1 and int(vs["arming_state"][i - 1]) == 2 and T(vs["timestamp"][i]) >= t_mis), None)
vc = ds("vehicle_command")
lead = next((T(vc["timestamp"][i]) for i in range(len(vc["timestamp"])) if int(vc["command"][i]) == 178 and int(vc["from_external"][i]) == 0 and T(vc["timestamp"][i]) > t_mis + 0.05), None)
if fin is None: fin = dis
gt, attg = ds("vehicle_local_position_groundtruth"), ds("vehicle_attitude_groundtruth")
lp, att, es, g, st = ds("vehicle_local_position"), ds("vehicle_attitude"), ds("estimator_states"), ds("estimator_aid_src_gnss_vel"), ds("estimator_status")
sa, vi, sc = ds("sensor_accel"), ds("vehicle_imu"), ds("sensor_combined")
# heading unit from truth 1 s before fin (acc3) or 0.5 s after mission start (off)
th = fin - 1.0 if mode == "acc3" else t_mis + 0.5
i0 = idx(gt, th); ux, uy = float(gt["vx"][i0]), float(gt["vy"][i0]); n = math.hypot(ux, uy); ux, uy = ux / n, uy / n
def tv(t):
    i = idx(gt, t); return float(gt["vx"][i]) * ux + float(gt["vy"][i]) * uy
def tlat(t):
    i = idx(gt, t); return -float(gt["vx"][i]) * uy + float(gt["vy"][i]) * ux
def tacc(t): return (tv(t + 0.1) - tv(t - 0.1)) / 0.2
def qg(t):
    i = idx(attg, t); return [float(attg[f"q[{k}]"][i]) for k in range(4)]
def qe(t):
    i = idx(att, t); return [float(att[f"q[{k}]"][i]) for k in range(4)]
# windows
t_dec = None
t = fin - 0.05
while t > fin - 8.0:
    if tacc(t) > -0.4: t_dec = t; break
    t -= 0.02
W = {}
if mode == "acc3":
    W["W0_cruise"] = (fin - 5.0, fin - 3.0); W["W1_brake"] = (fin - 2.5, fin - 0.05)
    if t_dec: W["W1f_fullbrake"] = (t_dec, fin - 0.05)
else:
    W["W1_brake_lead_to_fin"] = (lead if lead else fin - 2.0, fin - 0.05)
if dis and dis - 0.1 > fin + 0.8: W["W2_stop_armed"] = (fin + 0.8, dis - 0.1)
if dis: W["W3_disarmed"] = (dis + 0.3, dis + 2.5)

def accum(d, key_fn, lo, hi, use_sample=True):
    """sum over samples in window of R(q_truth(t)) * (vector * dt) + g*dt, projected; returns (dv_fwd, dv_lat, dv_down, n, dts)"""
    tsk = "timestamp_sample" if (use_sample and "timestamp_sample" in d) else "timestamp"
    ts = d[tsk]; out = [0.0, 0.0, 0.0]; nS = 0; dts = []; prev = None
    for i in range(len(ts)):
        t = T(ts[i])
        if t < lo or t > hi: continue
        vec, dt = key_fn(d, i, prev)
        prev = i
        if vec is None: continue
        r = q_rot(qg(t), vec)
        out[0] += r[0] + 0.0; out[1] += r[1]; out[2] += r[2] + G * dt
        nS += 1; dts.append(dt)
    fwd = out[0] * ux + out[1] * uy; lat = -out[0] * uy + out[1] * ux
    return fwd, lat, out[2], nS, dts

def f_sensor_accel(d, i, prev):
    if prev is None: return None, 0.0
    dt = (int(d["timestamp_sample"][i]) - int(d["timestamp_sample"][prev])) / 1e6
    if dt <= 0 or dt > 0.05: return None, 0.0
    return (float(d["x"][i]) * dt, float(d["y"][i]) * dt, float(d["z"][i]) * dt), dt
def f_vehicle_imu(d, i, prev):
    dt = float(d["delta_velocity_dt"][i]) / 1e6
    return (float(d["delta_velocity[0]"][i]), float(d["delta_velocity[1]"][i]), float(d["delta_velocity[2]"][i])), dt
def f_sensor_combined(d, i, prev):
    dt = float(d["accelerometer_integral_dt"][i]) / 1e6
    return (float(d["accelerometer_m_s2[0]"][i]) * dt, float(d["accelerometer_m_s2[1]"][i]) * dt, float(d["accelerometer_m_s2[2]"][i]) * dt), dt

def raw_stats(lo, hi):
    """sensor_combined 가 이 로그의 유일한 전율(250 Hz) IMU 기록 (sensor_accel 1 Hz·vehicle_imu 2 Hz 는 로거 감쇄). integral_dt 4000 us = 표본 1개 → raw 와 동일."""
    sel = [i for i in range(len(sc["timestamp"])) if lo <= T(sc["timestamp"][i]) <= hi]
    xs = [float(sc["accelerometer_m_s2[0]"][i]) for i in sel]
    if len(xs) < 8: return None
    m = sum(xs) / len(xs); sd = math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))
    tsr = [T(sc["timestamp"][i]) for i in sel]
    dtm = sorted(tsr[k + 1] - tsr[k] for k in range(len(tsr) - 1))[len(tsr) // 2]
    N = len(xs); det = [x - m for x in xs]
    peaks = []
    for k in range(1, N // 2):
        re = sum(det[j] * math.cos(2 * math.pi * k * j / N) for j in range(N)); im = sum(det[j] * math.sin(2 * math.pi * k * j / N) for j in range(N))
        peaks.append((math.hypot(re, im) * 2 / N, k / (N * dtm)))
    peaks.sort(reverse=True)
    clip = sum(1 for i in sel if int(sc["accelerometer_clipping"][i]))
    gy = sum(float(sc["gyro_rad[1]"][i]) * float(sc["gyro_integral_dt"][i]) / 1e6 for i in sel)
    zs = [float(sc["accelerometer_m_s2[2]"][i]) for i in sel]
    # 두 봉우리: 표본을 -2.5 기준으로 나눈 두 군의 평균·비율 (채터 수준)
    lowg = [x for x in xs if x < -2.5]; hig = [x for x in xs if x >= -2.5]
    # 희소 원시 표본(sensor_accel 1 Hz)과 같은 시각 combined 표본의 차 (동일성 확인)
    ident = []
    if sa is not None:
        for i in range(len(sa["timestamp"])):
            t = T(sa["timestamp_sample"][i])
            if lo <= t <= hi:
                j = idx(sc, t); ident.append(round(float(sa["x"][i]) - float(sc["accelerometer_m_s2[0]"][j]), 4))
    return {"n": N, "dt_med_ms": round(dtm * 1000, 3), "mean": round(m, 3), "sd": round(sd, 3), "min": round(min(xs), 2), "max": round(max(xs), 2),
            "frac_lt_m4": round(sum(1 for x in xs if x < -4) / N, 2), "frac_gt_m1": round(sum(1 for x in xs if x > -1) / N, 2),
            "bimodal_low_mean_frac": [round(sum(lowg) / len(lowg), 2) if lowg else None, round(len(lowg) / N, 2)], "bimodal_high_mean_frac": [round(sum(hig) / len(hig), 2) if hig else None, round(len(hig) / N, 2)],
            "z_mean_sd": [round(sum(zs) / N, 3), round(math.sqrt(sum((z - sum(zs) / N) ** 2 for z in zs) / N), 3)],
            "gyro_y_integrated_deg": round(math.degrees(gy), 3),
            "top_peaks_amp_hz": [[round(a, 2), round(f, 1)] for a, f in peaks[:4]], "clip_samples": clip, "sparse_sensor_accel_minus_combined": ident[:6]}

out = {"label": label, "ulg": ulg, "sha1": hashlib.sha1(open(ulg, "rb").read()).hexdigest(), "ver_sw": u.msg_info_dict.get("ver_sw"), "mode": mode,
       "t_mis": round(t_mis, 3), "lead_reached": None if lead is None else round(lead, 3), "fin": round(fin, 3), "disarm": None if dis is None else round(dis, 3),
       "t_dec": None if t_dec is None else round(t_dec, 3), "heading_unit_NE": [round(ux, 4), round(uy, 4)],
       "params": {k: P.get(k) for k in ("IMU_INTEG_RATE", "IMU_GYRO_RATEMAX", "IMU_ACCEL_CUTOFF", "SENS_IMU_MODE", "EKF2_PREDICT_US", "EKF2_GPS_V_NOISE", "EKF2_GPS_P_NOISE", "EKF2_ACC_NOISE", "EKF2_ACC_B_NOISE", "EKF2_ABL_LIM", "EKF2_ABL_TAU", "EKF2_GYR_NOISE", "EKF2_IMU_POS_X", "EKF2_IMU_POS_Y", "EKF2_IMU_POS_Z", "EKF2_GPS_CTRL", "EKF2_IMU_CTRL", "RA_ACC_RAD_MAX", "NAV_ACC_RAD", "SYS_AUTOSTART", "CAL_ACC0_XOFF", "CAL_ACC0_XSCALE", "CAL_ACC0_PRIO", "SDLOG_PROFILE")},
       "instances": {n: sorted({x.multi_id for x in u.data_list if x.name == n}) for n in ("estimator_states", "sensor_accel", "vehicle_imu", "sensor_combined", "vehicle_attitude_groundtruth")},
       "rates": {}, "windows": {}}
for n in ("sensor_accel", "vehicle_imu", "sensor_combined", "vehicle_local_position_groundtruth", "vehicle_attitude_groundtruth", "vehicle_local_position", "estimator_states", "estimator_aid_src_gnss_vel", "vehicle_gps_position"):
    d = ds(n)
    if d is None: continue
    ts = d["timestamp"]; dts = sorted((int(b) - int(a)) / 1e6 for a, b in zip(ts, ts[1:]))
    r = {"n": len(ts), "dt_med_ms": round(dts[len(dts) // 2] * 1000, 3), "dt_p99_ms": round(dts[int(0.99 * (len(dts) - 1))] * 1000, 3), "dt_max_ms": round(dts[-1] * 1000, 1)}
    if "timestamp_sample" in d:
        lag = sorted((int(a) - int(b)) / 1e6 for a, b in zip(d["timestamp"], d["timestamp_sample"])); r["ts_minus_sample_med_s"] = round(lag[len(lag) // 2], 4)
    if n == "vehicle_imu":
        dv = sorted(float(x) for x in d["delta_velocity_dt"]); r["dv_dt_med_us"] = dv[len(dv) // 2]; r["dv_dt_min_us"] = dv[0]; r["dv_dt_max_us"] = dv[-1]
        r["clip_any"] = sum(1 for x in d["delta_velocity_clipping"] if int(x))
    if n == "sensor_combined":
        dv = sorted(float(x) for x in d["accelerometer_integral_dt"]); r["integ_dt_med_us"] = dv[len(dv) // 2]; r["clip_any"] = sum(1 for x in d["accelerometer_clipping"] if int(x))
    out["rates"][n] = r

for wname, (lo, hi) in W.items():
    w = {"lo_rel_fin": round(lo - fin, 3), "hi_rel_fin": round(hi - fin, 3), "dur_s": round(hi - lo, 3)}
    w["truth_dv_fwd"] = round(tv(hi) - tv(lo), 3); w["truth_dv_lat"] = round(tlat(hi) - tlat(lo), 3)
    w["truth_dv_down"] = round(float(gt["vz"][idx(gt, hi)]) - float(gt["vz"][idx(gt, lo)]), 3)
    w["valid_const_speed_ref"] = abs((tv(hi) - tv(lo)) / (hi - lo)) <= 0.3
    w["truth_acc_mean"] = round((tv(hi) - tv(lo)) / (hi - lo), 3)
    w["truth_v_lo_hi"] = [round(tv(lo), 3), round(tv(hi), 3)]
    for sname, d, fn in (("sensor_accel", sa, f_sensor_accel), ("vehicle_imu", vi, f_vehicle_imu), ("sensor_combined", sc, f_sensor_combined)):
        if d is None: continue
        fwd, lat, dwn, nS, dts = accum(d, fn, lo, hi)
        exp_n = (hi - lo) / (out["rates"][sname]["dt_med_ms"] / 1000.0)
        w[sname] = {"dv_fwd": round(fwd, 3), "excess_fwd": round(fwd - w["truth_dv_fwd"], 3), "excess_rate_mps2": round((fwd - w["truth_dv_fwd"]) / (hi - lo), 3),
                    "dv_lat": round(lat, 3), "dv_down(+g corr)": round(dwn, 3), "n": nS, "n_expected": round(exp_n, 1), "sum_dt": round(sum(dts), 3),
                    "dt_max_ms": round(max(dts) * 1000, 2) if dts else None}
    rs = raw_stats(lo, hi)
    if rs: w["raw_x_stats"] = rs
    # attitude
    pe = [eul(qe(t))[1] for t in (lo, (lo + hi) / 2, hi)]; pt = [eul(qg(t))[1] for t in (lo, (lo + hi) / 2, hi)]
    w["pitch_ekf_lo_mid_hi"] = [round(x, 2) for x in pe]; w["pitch_truth_lo_mid_hi"] = [round(x, 2) for x in pt]; w["dpitch_lo_mid_hi"] = [round(a - b, 2) for a, b in zip(pe, pt)]
    w["roll_truth_mid"] = round(eul(qg((lo + hi) / 2))[0], 2)
    # EKF vs truth / GNSS
    def sig(d, kx, ky, t):
        i = idx(d, t); return float(d[kx][i]) * ux + float(d[ky][i]) * uy
    ts_grid = [lo + k * 0.05 for k in range(int((hi - lo) / 0.05) + 1)]
    e_lp = [sig(lp, "vx", "vy", t) - tv(t) for t in ts_grid]; e_st = [sig(es, "states[4]", "states[5]", t) - tv(t) for t in ts_grid]
    e_gn = [sig(g, "observation[0]", "observation[1]", t) - tv(t) for t in ts_grid]
    inn = [sig(g, "innovation[0]", "innovation[1]", t) for t in ts_grid]
    gi = [i for i in range(len(g["timestamp"])) if lo <= T(g["timestamp"][i]) <= hi]
    w["ekf_out_minus_truth_mean"] = round(sum(e_lp) / len(e_lp), 3); w["ekf_states_minus_truth_mean"] = round(sum(e_st) / len(e_st), 3)
    w["gnss_obs_minus_truth_mean"] = round(sum(e_gn) / len(e_gn), 3); w["gnss_innov_mean(state-obs)"] = round(sum(inn) / len(inn), 3)
    w["gnss_n"] = len(gi); w["gnss_fused"] = sum(int(g["fused"][i]) for i in gi) if "fused" in g else None; w["gnss_rejected"] = sum(int(g["innovation_rejected"][i]) for i in gi) if "innovation_rejected" in g else None
    out["windows"][wname] = w
# post-stop EKF response (acc3)
if mode == "acc3" and dis:
    seq = [(t, float(lp["vx"][idx(lp, t)]) * ux + float(lp["vy"][idx(lp, t)]) * uy) for t in [fin + k * 0.05 for k in range(6, int((dis - fin + 1.0) / 0.05))]]
    vmin = min(seq, key=lambda p: p[1]); vmax = max(seq, key=lambda p: p[1])
    zc = [round(seq[k][0] - fin, 2) for k in range(1, len(seq)) if seq[k - 1][1] * seq[k][1] < 0]
    out["post_stop"] = {"ekf_v_at_fin+0.6": round(seq[6][1], 3) if len(seq) > 6 else None, "min": [round(vmin[0] - fin, 2), round(vmin[1], 3)], "max": [round(vmax[0] - fin, 2), round(vmax[1], 3)], "zero_cross_rel_fin": zc[:4],
                        "truth_v_at_fin": round(tv(fin), 3), "ekf_out_at_fin": round(float(lp["vx"][idx(lp, fin)]) * ux + float(lp["vy"][idx(lp, fin)]) * uy, 3),
                        "dpitch_at_fin": round(eul(qe(fin))[1] - eul(qg(fin))[1], 2), "dpitch_at_max": round(eul(qe(vmax[0]))[1] - eul(qg(vmax[0]))[1], 2)}
json.dump(out, open(outp, "w"), indent=1)
ws = out["windows"]
def ex(wn, s="sensor_combined"): return ws.get(wn, {}).get(s, {}).get("excess_fwd")
def rate(wn): return ws.get(wn, {}).get("sensor_combined", {}).get("excess_rate_mps2")
w1 = "W1_brake" if "W1_brake" in ws else "W1_brake_lead_to_fin"
rs = ws.get(w1, {}).get("raw_x_stats", {})
print(f"{label}: fin {fin:.2f} dis {dis} | {w1} truth_dv {ws.get(w1,{}).get('truth_dv_fwd')} excess(comb) {ex(w1)} ({rate(w1)} m/s2) | W1f {ex('W1f_fullbrake')} | W0 {ex('W0_cruise')} valid {ws.get('W0_cruise',{}).get('valid_const_speed_ref')} "
      f"| W2 {ex('W2_stop_armed')} W3 {ex('W3_disarmed')} | raw mean/sd {rs.get('mean')}/{rs.get('sd')} lo {rs.get('bimodal_low_mean_frac')} hi {rs.get('bimodal_high_mean_frac')} gyroY {rs.get('gyro_y_integrated_deg')} peaks {rs.get('top_peaks_amp_hz')} "
      f"| dpitch {ws.get(w1,{}).get('dpitch_lo_mid_hi')} | innov {ws.get(w1,{}).get('gnss_innov_mean(state-obs)')} | post {out.get('post_stop',{}).get('max')}")
