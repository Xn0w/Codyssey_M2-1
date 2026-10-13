"""같은 IMU 표본(gz = PX4 sensor_accel, 오프셋 0 확인)에 자세 출처 3가지를 적용해 진행 방향 Δv 를 비교 — 분석 산물 여부 판별.
사용: python3 attitude_check.py <ulg> <gzrec_dir>
자세: (A) gz IMU orientation 필드 (B) gz pose/info 모델 자세 (C) PX4 vehicle_attitude_groundtruth (NED→ ENU 변환해 같은 축으로).
창: W_static [fin+0.8, fin+2.5], W_cruise [fin−5, fin−3], W1 [fin−2.5, fin−0.05]. truth Δv = gz pose 위치 차분 (진행 방향).
각 자세로 몸체 가속도(FLU, gz 원값) → 세계(ENU) 회전 → 중력 (0,0,9.8) 빼기 → 진행 방향 투영 적분. 피치(deg) 평균도 출처별로."""
import csv, math, sys
import numpy as np
from pyulog import ULog
u = ULog(sys.argv[1]); gd = sys.argv[2]
def ds(n): return [x for x in u.data_list if x.name == n and x.multi_id == 0][0].data
rows = list(csv.DictReader(open(gd + "/imu.csv"))); prow = list(csv.DictReader(open(gd + "/pose.csv")))
gs = np.array([float(r["stamp"]) for r in rows]); A = np.array([[float(r["ax"]), float(r["ay"]), float(r["az"])] for r in rows])
Qi = np.array([[float(r["qw"]), float(r["qx"]), float(r["qy"]), float(r["qz"])] for r in rows])
ps = np.array([float(r["stamp"]) for r in prow]); P = np.array([[float(r["x"]), float(r["y"])] for r in prow]); Qp = np.array([[float(r["qw"]), float(r["qx"]), float(r["qy"]), float(r["qz"])] for r in prow])
ag = ds("vehicle_attitude_groundtruth"); at = np.array(ag["timestamp_sample"] if "timestamp_sample" in ag else ag["timestamp"], float) * 1e-6
Qn = np.array([ag["q[0]"], ag["q[1]"], ag["q[2]"], ag["q[3]"]], float).T     # NED←FRD
mr = ds("mission_result"); ids = []
for k in range(len(mr["timestamp"])):
    i = int(mr["mission_id"][k])
    if i and (not ids or ids[-1] != i): ids.append(i)
fin = next(int(mr["timestamp"][k]) * 1e-6 for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == ids[-1] and int(mr["finished"][k]))
def R(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
NED2ENU = np.array([[0, 1, 0], [1, 0, 0], [0, 0, -1]]); FLU2FRD = np.diag([1, -1, -1])
k = np.searchsorted(ps, fin - 1.0); v = (P[k + 1] - P[k - 1]) / (ps[k + 1] - ps[k - 1]); uvec = v / np.linalg.norm(v)
def vel(t):
    k = min(max(np.searchsorted(ps, t), 1), len(ps) - 2); return float(np.dot((P[k + 1] - P[k - 1]) / (ps[k + 1] - ps[k - 1]), uvec))
def pitch_deg(Rm):
    fx = Rm @ np.array([1, 0, 0]); return math.degrees(math.asin(max(-1, min(1, fx[2]))))     # ENU 에서 기수 위 +
def run(lo, hi, src):
    sel = np.where((gs >= lo) & (gs <= hi))[0]; dv = 0.0; pit = []
    for i in sel:
        if src == "A": Rm = R(Qi[i])
        elif src == "B": Rm = R(Qp[min(np.searchsorted(ps, gs[i]), len(ps) - 1)])
        else: Rm = NED2ENU @ R(Qn[min(np.searchsorted(at, gs[i]), len(at) - 1)]) @ FLU2FRD
        a = Rm @ A[i] - np.array([0, 0, 9.8]); dt = (gs[i + 1] - gs[i]) if i + 1 < len(gs) else 0.004
        dv += float(np.dot(a[:2], uvec)) * dt; pit.append(pitch_deg(Rm))
    return round(dv, 4), round(float(np.mean(pit)), 3)
print("fin", round(fin, 3), "u", uvec.round(4))
for name, (lo, hi) in {"static": (fin + 0.8, fin + 2.5), "cruise": (fin - 5.0, fin - 3.0), "W1": (fin - 2.5, fin - 0.05)}.items():
    truth = round(vel(hi) - vel(lo), 4)
    res = {s: run(lo, hi, s) for s in "ABC"}
    print(name, "truth_dv", truth, " ".join(f"{s}: dv {r[0]} (E {round(r[0] - truth, 4)}) pitch {r[1]}" for s, r in res.items()))
