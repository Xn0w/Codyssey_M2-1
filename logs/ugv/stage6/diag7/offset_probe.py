"""gz IMU sim stamp ↔ PX4 sensor_accel hrt 오프셋 탐색: 4 ms 격자 시계열 상호상관 (x 축), ±150 s. 사용: python3 offset_probe.py <ulg> <gzrec_dir>"""
import csv, sys
import numpy as np
from pyulog import ULog
u = ULog(sys.argv[1]); sa = [x for x in u.data_list if x.name == "sensor_accel" and x.multi_id == 0][0].data
ht = np.array(sa["timestamp_sample"], float) * 1e-6; px = np.array(sa["x"], float)
rows = list(csv.DictReader(open(sys.argv[2] + "/imu.csv"))); gs = np.array([float(r["stamp"]) for r in rows]); gx = np.array([float(r["ax"]) for r in rows])
gk = np.round(gs / 0.004).astype(np.int64); hk = np.round(ht / 0.004).astype(np.int64)
print("gz stamp range", gs[0], gs[-1], "px4 hrt range", ht[0], ht[-1], "n", len(gs), len(ht))
gmap = dict(zip(gk.tolist(), gx.tolist()))
best = []
for lag in range(int((ht[0] - gs[-1]) / 0.004) - 10, int((ht[-1] - gs[0]) / 0.004) + 10, 1):
    keys = hk[::25] - lag
    vals = [(gmap.get(int(k)), p) for k, p in zip(keys, px[::25])]
    vals = [(a, b) for a, b in vals if a is not None]
    if len(vals) < 200: continue
    e = np.median([abs(a - b) for a, b in vals])
    best.append((e, lag, len(vals)))
best.sort()
print("best lags (median|err|, lag_samples, offset_s, n):", [(round(e, 5), l, round(l * 0.004, 3), n) for e, l, n in best[:5]])
e, lag, n = best[0]
keys = hk - lag; m = np.array([int(k) in gmap for k in keys]); d = np.array([gmap[int(k)] - p for k, p in zip(keys[m], px[m])])
print("at best: matched", m.mean().round(4), "exact<1e-4", np.mean(np.abs(d) < 1e-4).round(4), "median", np.median(np.abs(d)), "p99", np.percentile(np.abs(d), 99), "max", np.abs(d).max())
