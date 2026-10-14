"""진단 7 분석 증거 v2 (Codex 0605 2절). 사용: python3 diag7_evidence_v2.py <ulg> <gzrec_dir> <out.json> [--virtual250]
- 올바른 자세(gz pose/info 모델 자세, PX4 groundtruth 와 교차 확인) 로 E 를 W_static/W_cruise/W1 에서 계산해 기계 판독 JSON 으로.
- 브리지 대응: gz·PX4 시작/끝·중첩 구간, 중첩 기대 표본 수·일치 수·실제 timestamp 오차(키 반올림과 별개) 를 전체·W1·정지 창별로.
- --virtual250: 500 Hz 자료에서 2 ms 격자 짝/홀 표본만 골라 4 ms 표본화처럼 적분한 E250_even/odd (같은 물리 궤적의 측정 반사실).
- 20 ms 위상(표본 간격 단위) 별 평균·적분 기여. gz IMU orientation 필드는 쓰지 않는다 (진단 7 에서 방위 규약 불일치 확인)."""
import csv, hashlib, json, math, sys
import numpy as np
from pyulog import ULog
ulg, gd, outp = sys.argv[1], sys.argv[2], sys.argv[3]; virt = "--virtual250" in sys.argv
u = ULog(ulg)
def ds(n): return [x for x in u.data_list if x.name == n and x.multi_id == 0][0].data
rows = list(csv.DictReader(open(gd + "/imu.csv"))); prow = list(csv.DictReader(open(gd + "/pose.csv")))
gs = np.array([float(r["stamp"]) for r in rows]); A = np.array([[float(r["ax"]), float(r["ay"]), float(r["az"])] for r in rows])
ps = np.array([float(r["stamp"]) for r in prow]); P = np.array([[float(r["x"]), float(r["y"])] for r in prow])
Qp = np.array([[float(r["qw"]), float(r["qx"]), float(r["qy"]), float(r["qz"])] for r in prow])
sa = ds("sensor_accel"); ht = np.array(sa["timestamp_sample"], float) * 1e-6; PX = np.array([sa["x"], sa["y"], sa["z"]], float).T
mr = ds("mission_result"); ids = []
for k in range(len(mr["timestamp"])):
    i = int(mr["mission_id"][k])
    if i and (not ids or ids[-1] != i): ids.append(i)
fin = next(int(mr["timestamp"][k]) * 1e-6 for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == ids[-1] and int(mr["finished"][k]))
step = float(np.median(np.diff(gs)))
out = {"ulg": ulg, "ulg_sha1": hashlib.sha1(open(ulg, "rb").read()).hexdigest(), "gzrec": gd, "fin_s": round(fin, 4), "gz_imu_step_s": round(step, 6),
       "attitude_source": "gz pose/info 모델 자세 (PX4 vehicle_attitude_groundtruth 와 진단 7 에서 값 일치 확인)", "sign": "E = IMU Δv − truth Δv, 음수 = 과대 감속"}
# 브리지 대응
lo_o, hi_o = max(gs[0], ht[0]), min(gs[-1], ht[-1])
def bridge(lo, hi):
    gsel = (gs >= lo) & (gs <= hi); hsel = (ht >= lo) & (ht <= hi)
    j = np.searchsorted(gs, ht[hsel]); j = np.clip(j, 1, len(gs) - 1)
    near = np.where(np.abs(gs[j - 1] - ht[hsel]) < np.abs(gs[j] - ht[hsel]), j - 1, j)
    dt = np.abs(gs[near] - ht[hsel]); m = dt < step / 4
    g = A[near][m]; p = PX[hsel][m]
    err = np.max(np.abs(np.stack([g[:, 0] - p[:, 0], -g[:, 1] - p[:, 1], -g[:, 2] - p[:, 2]], 1)), 1) if len(g) else np.array([])
    return {"window": [round(lo, 3), round(hi, 3)], "gz_samples": int(gsel.sum()), "px4_samples": int(hsel.sum()),
            "matched": int(m.sum()), "max_stamp_err_s": float(dt[m].max()) if m.any() else None,
            "max_value_err": float(err.max()) if len(err) else None, "frac_value_err_lt_1e-4": float(np.mean(err < 1e-4)) if len(err) else None}
out["bridge"] = {"gz_range": [round(gs[0], 3), round(gs[-1], 3)], "px4_range": [round(ht[0], 3), round(ht[-1], 3)], "overlap": bridge(lo_o, hi_o),
                 "W1": bridge(fin - 2.5, fin - 0.05), "static": bridge(fin + 0.8, fin + 2.5),
                 "note": "중첩 밖 표본은 비교 불가 (PX4 로그가 gz 기록보다 늦게 시작·일찍 끝남) — 핵심 구간 대응만 결론에 사용"}
def R(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
k = np.searchsorted(ps, fin - 1.0); v = (P[k + 1] - P[k - 1]) / (ps[k + 1] - ps[k - 1]); uvec = v / np.linalg.norm(v)
def vel(t):
    k = min(max(np.searchsorted(ps, t), 1), len(ps) - 2); return float(np.dot((P[k + 1] - P[k - 1]) / (ps[k + 1] - ps[k - 1]), uvec))
afwd = np.array([float(np.dot((R(Qp[min(np.searchsorted(ps, gs[i]), len(ps) - 1)]) @ A[i] - np.array([0, 0, 9.8]))[:2], uvec)) for i in range(len(gs))])
def E(lo, hi, pick=None, dt_override=None):
    sel = np.where((gs >= lo) & (gs <= hi))[0]
    if pick is not None: sel = sel[pick(sel)]
    if len(sel) < 2: return None
    dts = np.diff(np.append(gs[sel], gs[sel][-1] + (dt_override or step))) if dt_override is None else np.full(len(sel), dt_override)
    dv = float(np.sum(afwd[sel] * dts)); truth = vel(hi) - vel(lo)
    return {"dv_imu": round(dv, 4), "dv_truth": round(truth, 4), "E": round(dv - truth, 4), "n": int(len(sel))}
W = {"static": (fin + 0.8, fin + 2.5), "cruise": (fin - 5.0, fin - 3.0), "W1": (fin - 2.5, fin - 0.05)}
out["E"] = {w: E(*b) for w, b in W.items()}
if virt and step < 0.003:
    key = np.round(gs / step).astype(np.int64)
    for name, par in (("even", 0), ("odd", 1)):
        out.setdefault("E250_virtual", {})[name] = {w: E(*b, pick=lambda s, par=par: (key[s] % 2) == par, dt_override=2 * step) for w, b in W.items()}
    out["E250_virtual_note"] = "같은 물리 궤적에서 2 ms 격자 짝/홀 표본만 골라 4 ms 로 적분한 측정 반사실 — 250 Hz 폐루프 운행 결과 아님"
# 20 ms 위상별 (W1)
lo, hi = W["W1"]; sel = np.where((gs >= lo) & (gs <= hi))[0]; nph = int(round(0.020 / step))
ph = (np.round(gs[sel] / step).astype(np.int64)) % nph
out["phase20ms_W1"] = {"slots": nph, "mean_fwd_acc": [round(float(afwd[sel][ph == s].mean()), 3) for s in range(nph)],
                       "dv_contrib": [round(float(afwd[sel][ph == s].sum() * step), 4) for s in range(nph)]}
json.dump(out, open(outp, "w"), indent=1, ensure_ascii=False)
print(json.dumps({"E": out["E"], "E250_virtual": out.get("E250_virtual"), "bridge_W1": out["bridge"]["W1"], "bridge_static": out["bridge"]["static"], "phase": out["phase20ms_W1"]}, ensure_ascii=False))
