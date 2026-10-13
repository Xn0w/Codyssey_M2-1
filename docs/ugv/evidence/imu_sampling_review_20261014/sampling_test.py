"""표본화 가설 정량 검토 — gz 기록(imu.csv 4/2 ms, pose.csv 18 ms, joint.csv 2 ms, cmd.csv wall) 만으로 (WSL python3 + numpy, 읽기 전용).
사용: python3 sampling_test.py <gzrec_dir> <fin_sim_s> <label> <out.json>
- 물리 스텝(2 ms) 가속도 재구성: 네 바퀴 관절 속도 평균 × r(0.35) 의 스텝 차분 (속도 제어 바퀴 → 차체 속도 근사; pose 차분과의 일치로 검증).
- IMU 표본 ↔ 스텝 대응: 각 IMU 표본(stamp)에 스텝 k = round(stamp/0.002). 모델 (i) 같은 스텝 순간값, (ii) 직전 스텝, (iii) 두 스텝 평균 — 어느 것이 IMU 값과 맞는지 (W1 상관·RMS).
- 반사실: 관절 가속도로 '짝/홀 스텝만 4 ms 가중' 적분 → E_pred_even/odd; 기록 IMU 의 위상과 비교. d8(2 ms IMU) 는 IMU 자체로 짝/홀 반사실.
- 20 ms 틀(10 스텝) 슬롯별 관절 가속도·IMU 가속도 평균, 충격(관절 속도 점프) 시각·간격·슬롯, cmd.csv(wall) 값 열과 관절 속도 수준 열 대응.
E = Δv_imu − Δv_truth(pose) [m/s], 음수 = 과대 감속. 중력: ENU (0,0,−9.8), a = R(q_pose)·f + g.
"""
import csv, hashlib, json, math, sys
import numpy as np

gd, fin, label, outp = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4]
STEP = 0.002; R_WHEEL = 0.35
def sha(p): return hashlib.sha1(open(p, "rb").read()).hexdigest()
imu = list(csv.DictReader(open(gd + "/imu.csv"))); pose = list(csv.DictReader(open(gd + "/pose.csv")))
gs = np.array([float(r["stamp"]) for r in imu]); A = np.array([[float(r["ax"]), float(r["ay"]), float(r["az"])] for r in imu])
ps = np.array([float(r["stamp"]) for r in pose]); P = np.array([[float(r["x"]), float(r["y"]), float(r["z"])] for r in pose])
Q = np.array([[float(r["qw"]), float(r["qx"]), float(r["qy"]), float(r["qz"])] for r in pose])
imu_step = float(np.median(np.diff(gs)))
# joints: only around the windows to limit memory
lo_all, hi_all = fin - 6.0, fin + 3.0
J = {}
for r in csv.DictReader(open(gd + "/joint.csv")):
    t = float(r["stamp"])
    if lo_all <= t <= hi_all and "wheel" in r["name"] and "steer" not in r["name"]:
        J.setdefault(r["name"], []).append((t, float(r["vel"])))
names = sorted(J); JT = np.array([x[0] for x in J[names[0]]])
JV = np.mean([np.array([x[1] for x in J[n]])[:len(JT)] for n in names], axis=0)
def R(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
k0 = np.searchsorted(ps, fin - 1.0); vref = (P[k0 + 1, :2] - P[k0 - 1, :2]) / (ps[k0 + 1] - ps[k0 - 1]); u = vref / np.linalg.norm(vref)
def vtruth(t):
    k = min(max(np.searchsorted(ps, t), 1), len(ps) - 2); return float(np.dot((P[k + 1, :2] - P[k - 1, :2]) / (ps[k + 1] - ps[k - 1]), u))
G = np.array([0, 0, -9.8])
pidx = np.clip(np.searchsorted(ps, gs), 0, len(ps) - 1)
afwd = np.array([float(np.dot((R(Q[pidx[i]]) @ A[i] + G)[:2], u)) for i in range(len(gs))])
# wheel-based body speed sign: match sign with truth speed at fin-1
vj = JV * R_WHEEL
sgn = 1.0 if np.dot(vj[np.searchsorted(JT, fin - 1.0)], 1.0) * vtruth(fin - 1.0) >= 0 else -1.0
vj *= sgn
aj = np.diff(vj) / np.diff(JT); ajt = JT[1:]          # acceleration attributed to the step ending at JT[k]
kstep = np.round(ajt / STEP).astype(np.int64)
W = {"cruise": (fin - 5.0, fin - 3.0), "W1": (fin - 2.5, fin - 0.05), "static": (fin + 0.8, fin + 2.5)}
out = {"label": label, "gzrec": gd, "sha1": {f: sha(gd + "/" + f) for f in ("imu.csv", "pose.csv", "joint.csv", "cmd.csv")}, "fin_s": fin, "imu_step_s": round(imu_step, 6),
       "joint_names": names, "joint_step_med_s": round(float(np.median(np.diff(JT))), 6), "heading_unit_ENU": [round(float(u[0]), 4), round(float(u[1]), 4)], "windows": {}}
def Eimu(lo, hi, pick=None, dt=None):
    sel = np.where((gs >= lo) & (gs <= hi))[0]
    if pick is not None: sel = sel[pick(sel)]
    d = dt if dt is not None else imu_step
    return float(np.sum(afwd[sel]) * d), int(len(sel))
def Ej(lo, hi, parity=None, dt=STEP):
    sel = np.where((ajt >= lo) & (ajt <= hi))[0]
    if parity is not None: sel = sel[(kstep[sel] % 2) == parity]
    return float(np.sum(aj[sel]) * dt), int(len(sel))
for wn, (lo, hi) in W.items():
    w = {"lo": round(lo, 3), "hi": round(hi, 3), "truth_dv": round(vtruth(hi) - vtruth(lo), 4), "truth_v_lo_hi": [round(vtruth(lo), 3), round(vtruth(hi), 3)]}
    dv, n = Eimu(lo, hi); w["imu_dv"] = round(dv, 4); w["E_imu"] = round(dv - w["truth_dv"], 4); w["imu_n"] = n
    dvj, nj = Ej(lo, hi); w["joint_dv_allsteps"] = round(dvj, 4); w["E_joint_allsteps"] = round(dvj - w["truth_dv"], 4); w["joint_n"] = nj
    w["joint_speed_lo_hi"] = [round(float(vj[np.searchsorted(JT, lo)]), 3), round(float(vj[np.searchsorted(JT, hi)]), 3)]
    for par, nm in ((0, "even"), (1, "odd")):
        d2, n2 = Ej(lo, hi, parity=par, dt=2 * STEP); w[f"E_pred_from_joint_{nm}_steps_x4ms"] = round(d2 - w["truth_dv"], 4)
    # IMU sample phase (which step parity the IMU samples fall on) and IMU-vs-step model fit
    sel = np.where((gs >= lo) & (gs <= hi))[0]
    ki = np.round(gs[sel] / STEP).astype(np.int64)
    w["imu_step_parity_counts"] = {str(p): int(np.sum(ki % 2 == p)) for p in (0, 1)}
    jmap = {int(k): float(a) for k, a in zip(kstep, aj)}
    same = np.array([jmap.get(int(k), np.nan) for k in ki]); prev = np.array([jmap.get(int(k) - 1, np.nan) for k in ki]); nxt = np.array([jmap.get(int(k) + 1, np.nan) for k in ki])
    av2 = (same + prev) / 2; av2n = (same + nxt) / 2
    ok = ~np.isnan(same) & ~np.isnan(prev) & ~np.isnan(nxt)
    x = afwd[sel][ok]
    def fit(y):
        y = y[ok]; return {"rms": round(float(np.sqrt(np.mean((x - y) ** 2))), 3), "corr": round(float(np.corrcoef(x, y)[0, 1]), 3), "mean_imu_minus_model": round(float(np.mean(x - y)), 3)}
    w["imu_vs_joint_step_models"] = {"same_step": fit(same), "prev_step": fit(prev), "next_step": fit(nxt), "avg_same_prev": fit(av2), "avg_same_next": fit(av2n), "n": int(ok.sum())}
    if imu_step < 0.003:   # 500 Hz IMU: own even/odd counterfactual
        for par, nm in ((0, "even"), (1, "odd")):
            d2, n2 = Eimu(lo, hi, pick=lambda s, par=par: (np.round(gs[s] / STEP).astype(np.int64) % 2) == par, dt=2 * STEP)
            w[f"E_imu_virtual250_{nm}"] = round(d2 - w["truth_dv"], 4)
    # 20 ms slot structure (10 physics-step slots), joint accel and IMU accel
    selj = np.where((ajt >= lo) & (ajt <= hi))[0]; slot_j = kstep[selj] % 10
    w["slot20ms_joint_acc_mean"] = [round(float(np.mean(aj[selj][slot_j == s])), 2) if np.any(slot_j == s) else None for s in range(10)]
    slot_i = ki % 10
    w["slot20ms_imu_acc_mean"] = [round(float(np.mean(afwd[sel][slot_i == s])), 2) if np.any(slot_i == s) else None for s in range(10)]
    w["slot20ms_imu_n"] = [int(np.sum(slot_i == s)) for s in range(10)]
    # impulses in joint speed: steps where |dv| > 4 * median|dv|
    dv_step = np.diff(vj)[selj - 1] if len(selj) else np.array([])
    out["windows"][wn] = w
# impulse / command application timing over W1
lo, hi = W["W1"]; selj = np.where((ajt >= lo) & (ajt <= hi))[0]
dvs = np.abs(aj[selj]) * STEP; thr = 4 * np.median(dvs) if len(dvs) else 0
imp = selj[dvs > thr]
imp_t = ajt[imp]; gaps = np.diff(imp_t)
out["impulses_W1"] = {"threshold_dv_mps": round(float(thr), 4), "n": int(len(imp)), "gap_med_ms": round(float(np.median(gaps)) * 1000, 2) if len(gaps) else None,
                      "gap_hist_ms": {str(int(round(g * 1000))): int(c) for g, c in zip(*np.unique(np.round(gaps, 3), return_counts=True))} if len(gaps) else {},
                      "slot_hist": {str(int(s)): int(c) for s, c in zip(*np.unique(kstep[imp] % 10, return_counts=True))} if len(imp) else {},
                      "mean_dv_at_impulse": round(float(np.mean(aj[imp] * STEP)), 4) if len(imp) else None,
                      "first_10": [[round(float(t), 4), round(float(aj[i] * STEP), 4)] for t, i in zip(imp_t[:10], imp[:10])]}
# wheel speed level changes vs cmd.csv values (wall) — count of distinct command values per second and joint level steps
cmd = list(csv.DictReader(open(gd + "/cmd.csv")))
cw = np.array([float(r["wall"]) for r in cmd]); cv = np.array([float(r["v0"]) for r in cmd])
out["cmd_csv"] = {"n": len(cmd), "wall_dt_med_ms": round(float(np.median(np.diff(cw))) * 1000, 1), "wall_dt_p10_p90_ms": [round(float(np.percentile(np.diff(cw), 10)) * 1000, 1), round(float(np.percentile(np.diff(cw), 90)) * 1000, 1)],
                  "stamp_nonzero": int(np.sum(np.array([float(r["stamp"]) for r in cmd]) != 0)), "v0_changes_frac": round(float(np.mean(np.diff(cv) != 0)), 3)}
# joint velocity level changes (any step with |dv| > 1e-6) rate in W1
dvall = np.abs(np.diff(vj))[selj - 1]
out["joint_W1"] = {"frac_steps_with_change_gt_1e-4": round(float(np.mean(dvall > 1e-4)), 3), "frac_steps_with_change_gt_1e-2": round(float(np.mean(dvall > 1e-2)), 3), "dv_step_median": round(float(np.median(dvall)), 5), "dv_step_p95": round(float(np.percentile(dvall, 95)), 4)}
json.dump(out, open(outp, "w"), indent=1, ensure_ascii=False)
w1 = out["windows"]["W1"]
print(f"{label}: imu_step {imu_step*1000:.1f} ms | W1 truth {w1['truth_dv']} E_imu {w1['E_imu']} E_joint_all {w1['E_joint_allsteps']} | pred from joint even/odd {w1['E_pred_from_joint_even_steps_x4ms']}/{w1['E_pred_from_joint_odd_steps_x4ms']} | imu parity {w1['imu_step_parity_counts']} | fits {w1['imu_vs_joint_step_models']} | virt250 {w1.get('E_imu_virtual250_even')}/{w1.get('E_imu_virtual250_odd')} | slots joint {w1['slot20ms_joint_acc_mean']} imu {w1['slot20ms_imu_acc_mean']} | impulses {out['impulses_W1']['n']} gap {out['impulses_W1']['gap_med_ms']} slots {out['impulses_W1']['slot_hist']} | cmd wall dt {out['cmd_csv']['wall_dt_med_ms']} | static E {out['windows']['static']['E_imu']} joint {out['windows']['static']['E_joint_allsteps']}")
