"""PX4 sensor_accel 이 gz 500 Hz 의 어느 위상 표본인지, PX4 표본만으로 같은 창·자세(gz pose) E 를 계산. 사용: python3 px4_parity.py <ulg> <gzrec_dir>"""
import csv, sys
import numpy as np
from pyulog import ULog
u = ULog(sys.argv[1]); gd = sys.argv[2]
d = lambda n: [x for x in u.data_list if x.name == n and x.multi_id == 0][0].data
sa = d("sensor_accel"); ht = np.array(sa["timestamp_sample"], float) * 1e-6; PX = np.array([sa["x"], sa["y"], sa["z"]], float).T
rows = list(csv.DictReader(open(gd + "/imu.csv"))); gs = np.array([float(r["stamp"]) for r in rows])
step = float(np.median(np.diff(gs))); key = np.round(gs / step).astype(np.int64)
hk = np.round(ht / step).astype(np.int64)
print("gz step", step, "PX4 key parity counts", {p: int(np.sum(hk % 2 == p)) for p in (0, 1)})
prow = list(csv.DictReader(open(gd + "/pose.csv"))); ps = np.array([float(r["stamp"]) for r in prow]); P = np.array([[float(r["x"]), float(r["y"])] for r in prow]); Q = np.array([[float(r[k]) for k in ("qw", "qx", "qy", "qz")] for r in prow])
mr = d("mission_result"); ids = []
for k in range(len(mr["timestamp"])):
    i = int(mr["mission_id"][k])
    if i and (not ids or ids[-1] != i): ids.append(i)
fin = next(int(mr["timestamp"][k]) * 1e-6 for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == ids[-1] and int(mr["finished"][k]))
def R(q):
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
k = np.searchsorted(ps, fin - 1.0); v = (P[k + 1] - P[k - 1]) / (ps[k + 1] - ps[k - 1]); uv = v / np.linalg.norm(v)
def vel(t):
    k = min(max(np.searchsorted(ps, t), 1), len(ps) - 2); return float(np.dot((P[k + 1] - P[k - 1]) / (ps[k + 1] - ps[k - 1]), uv))
lo, hi = fin - 2.5, fin - 0.05
sel = np.where((ht >= lo) & (ht <= hi))[0]
dv = 0.0
for i in sel:
    a_flu = np.array([PX[i, 0], -PX[i, 1], -PX[i, 2]])
    a = R(Q[min(np.searchsorted(ps, ht[i]), len(ps) - 1)]) @ a_flu - np.array([0, 0, 9.8]); dv += float(np.dot(a[:2], uv)) * 0.004
print("PX4 sensor_accel 만 (4 ms) E W1:", round(dv - (vel(hi) - vel(lo)), 4), "n", len(sel), "parity of PX4 samples in W1", {p: int(np.sum(hk[sel] % 2 == p)) for p in (0, 1)})
