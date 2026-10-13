"""(B) 동일 기준 단계 비교 — gz IMU 500 Hz (imu.csv) vs PX4 sensor_combined(4 ms, 2 표본 적분) vs PX4 로거 sensor_accel(홀수 위상):
같은 시간 경계(PX4 combined timestamp 격자 = 적분 구간 끝), 같은 자세 소스(gz pose/info 모델 자세), 같은 truth(gz pose 중앙 차분), 실제 dt.
사용: python3 stage_compare.py <ulg> <gzrec_dir> <fin_sim> <out.json>   (WSL python3 + numpy + pyulog)
또한 (A) 보조: PX4 combined 가속도 = 같은 구간의 gz 2 표본 평균인가(짝+홀) / 홀수 표본 하나인가 — 표본 단위 대조.
"""
import csv, hashlib, json, sys
import numpy as np
from pyulog import ULog
ulg, gd, fin, outp = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
u = ULog(ulg)
def ds(n): return [x for x in u.data_list if x.name == n and x.multi_id == 0][0].data
sc = ds("sensor_combined"); sa = ds("sensor_accel"); vi = ds("vehicle_imu"); vs = ds("vehicle_imu_status")
ct = np.array(sc["timestamp"], float) * 1e-6; cdt = np.array(sc["accelerometer_integral_dt"], float) * 1e-6
cA = np.array([sc["accelerometer_m_s2[0]"], sc["accelerometer_m_s2[1]"], sc["accelerometer_m_s2[2]"]], float).T
st_ = np.array(sa["timestamp_sample"], float) * 1e-6; sA = np.array([sa["x"], sa["y"], sa["z"]], float).T
rows = list(csv.DictReader(open(gd + "/imu.csv"))); gs = np.array([float(r["stamp"]) for r in rows]); gA = np.array([[float(r["ax"]), float(r["ay"]), float(r["az"])] for r in rows])
prow = list(csv.DictReader(open(gd + "/pose.csv"))); ps = np.array([float(r["stamp"]) for r in prow]); P = np.array([[float(r["x"]), float(r["y"])] for r in prow])
Q = np.array([[float(r["qw"]), float(r["qx"]), float(r["qy"]), float(r["qz"])] for r in prow])
step = float(np.median(np.diff(gs)))
def R(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
k = np.searchsorted(ps, fin - 1.0); v = (P[k + 1] - P[k - 1]) / (ps[k + 1] - ps[k - 1]); uv = v / np.linalg.norm(v)
def vel(t):
    k = min(max(np.searchsorted(ps, t), 1), len(ps) - 2); return float(np.dot((P[k + 1] - P[k - 1]) / (ps[k + 1] - ps[k - 1]), uv))
def fwd_flu(a_flu, t):
    return float(np.dot((R(Q[min(np.searchsorted(ps, t), len(ps) - 1)]) @ a_flu - np.array([0, 0, 9.8]))[:2], uv))
def frd2flu(a): return np.array([a[0], -a[1], -a[2]])
out = {"ulg": ulg, "ulg_sha1": hashlib.sha1(open(ulg, "rb").read()).hexdigest(), "gzrec": gd, "fin": fin, "gz_step_s": step,
       "vehicle_imu_status_accel_rate_hz": [float(x) for x in np.unique(np.round(np.array(vs["accel_rate_hz"], float)))] if "accel_rate_hz" in vs else None,
       "vehicle_imu_dv_dt_us_unique": [float(x) for x in np.unique(np.array(vi["delta_velocity_dt"], float))][:5],
       "logger_sensor_accel_dt_med_s": float(np.median(np.diff(st_))), "logger_sensor_accel_parity_counts": {str(p): int(np.sum(np.round(st_ / step).astype(np.int64) % 2 == p)) for p in (0, 1)}}
lo, hi = fin - 2.5, fin - 0.05
# 1) 기준 경계: PX4 combined 표본 (timestamp = 적분 끝) 중 lo < t <= hi → 각 표본의 적분 구간 [t - dt, t]
csel = np.where((ct > lo) & (ct <= hi))[0]
t_lo_eff, t_hi_eff = float(ct[csel[0]] - cdt[csel[0]]), float(ct[csel[-1]])
truth = vel(t_hi_eff) - vel(t_lo_eff)
# PX4 combined: 가속도 × 실제 dt, 자세 = gz pose at 구간 중점
dv_comb = sum(fwd_flu(frd2flu(cA[i]), ct[i] - cdt[i] / 2) * cdt[i] for i in csel)
# gz 500 Hz 전 표본 in (t_lo_eff, t_hi_eff]: 표본 stamp 는 그 스텝의 값; 적분 dt = step
gsel = np.where((gs > t_lo_eff) & (gs <= t_hi_eff))[0]
dv_gz = sum(fwd_flu(gA[i], gs[i]) * step for i in gsel)
# gz 2표본 평균을 combined 격자로 묶어 적분 (PX4 적분 모사)
dv_gz_pairs = 0.0; pair_rows = []
for i in csel:
    m = (gs > ct[i] - cdt[i] + 1e-9) & (gs <= ct[i] + 1e-9)
    if m.sum() == 0: continue
    a_mean = gA[m].mean(axis=0); dv_gz_pairs += fwd_flu(a_mean, ct[i] - cdt[i] / 2) * cdt[i]
    a_px4_flu = frd2flu(cA[i]); last = gA[m][-1]
    pair_rows.append([round(float(ct[i]), 4), int(m.sum()), round(float(a_mean[0]), 4), round(float(last[0]), 4), round(float(a_px4_flu[0]), 4)])
pr = np.array([[r[2], r[3], r[4]] for r in pair_rows]) if pair_rows else np.zeros((0, 3))
# 로거 sensor_accel (홀수 위상) 만: 4 ms 가중
ssel = np.where((st_ > t_lo_eff) & (st_ <= t_hi_eff))[0]
dv_sa = sum(fwd_flu(frd2flu(sA[i]), st_[i]) * (2 * step) for i in ssel)
out["same_basis_W1"] = {"t_lo_eff": round(t_lo_eff, 4), "t_hi_eff": round(t_hi_eff, 4), "truth_dv": round(truth, 4),
                        "E_px4_combined_realdt": round(dv_comb - truth, 4), "n_comb": int(len(csel)), "sum_dt_comb": round(float(cdt[csel].sum()), 4),
                        "E_gz_all_2ms": round(dv_gz - truth, 4), "n_gz": int(len(gsel)),
                        "E_gz_pair_mean_x_combdt": round(dv_gz_pairs - truth, 4), "pairs_with_2": int(sum(1 for r in pair_rows if r[1] == 2)), "pairs_other": int(sum(1 for r in pair_rows if r[1] != 2)),
                        "E_logger_sensor_accel_x4ms": round(dv_sa - truth, 4), "n_sa": int(len(ssel)),
                        "px4_combined_vs_gz_pair_mean_x: rms/max": [round(float(np.sqrt(np.mean((pr[:, 2] - pr[:, 0]) ** 2))), 5), round(float(np.max(np.abs(pr[:, 2] - pr[:, 0]))), 5)] if len(pr) else None,
                        "px4_combined_vs_gz_last_sample_x: rms/max": [round(float(np.sqrt(np.mean((pr[:, 2] - pr[:, 1]) ** 2))), 5), round(float(np.max(np.abs(pr[:, 2] - pr[:, 1]))), 5)] if len(pr) else None}
# 2) 원래 두 정의 재현: evidence_v2 (gz stamps in [lo,hi], dt step, truth vel(hi)-vel(lo)) vs imu_cause-like (PX4 combined timestamps in [lo,hi], dt real, truth from groundtruth)
gsel0 = np.where((gs >= lo) & (gs <= hi))[0]; E_v2 = sum(fwd_flu(gA[i], gs[i]) * step for i in gsel0) - (vel(hi) - vel(lo))
csel0 = np.where((ct >= lo) & (ct <= hi))[0]; E_ic_like = sum(fwd_flu(frd2flu(cA[i]), ct[i]) * cdt[i] for i in csel0) - (vel(hi) - vel(lo))
gt = ds("vehicle_local_position_groundtruth"); gtt = np.array(gt["timestamp"], float) * 1e-6
def vgt(t):
    i = int(np.argmin(np.abs(gtt - t))); return float(gt["vx"][i]) * (-uv[1] if False else 0) + 0  # placeholder (NED/ENU 축 다름) — 아래서 속도 크기 비교만
out["original_definitions"] = {"E_evidence_v2_recomputed": round(E_v2, 4), "n": int(len(gsel0)),
                               "E_imu_cause_like(px4_comb, gz_truth_central)": round(E_ic_like, 4), "n": int(len(csel0)),
                               "boundary_note": "imu_cause 는 PX4 groundtruth vx,vy(브리지 후방 차분 18 ms) 를 truth 로, 창 끝 표본 포함 규칙이 다름; 여기서는 동일 truth(gz pose 중앙 차분) 로 재계산"}
# truth 차: groundtruth 후방 차분 vs pose 중앙 차분 at window edges (속도 크기)
sp_gt = np.hypot(np.array(gt["vx"], float), np.array(gt["vy"], float))
def sgt(t): return float(sp_gt[int(np.argmin(np.abs(gtt - t)))])
out["truth_source_diff"] = {"edge_lo": round(sgt(lo) - abs(vel(lo)), 4), "edge_hi": round(sgt(hi) - abs(vel(hi)), 4), "note": "PX4 groundtruth(후방 차분, 수신 시각) 속도 크기 − gz pose 중앙 차분 속도"}
json.dump(out, open(outp, "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: out[k] for k in ("vehicle_imu_status_accel_rate_hz", "vehicle_imu_dv_dt_us_unique", "logger_sensor_accel_dt_med_s", "logger_sensor_accel_parity_counts", "same_basis_W1", "original_definitions", "truth_source_diff")}, ensure_ascii=False))
