"""제동 창의 바퀴 관절 속도(2 ms)·gz IMU x(4 ms) 의 스텝 간 교대·위상 확인. 사용: python3 joint_alias.py <gzrec_dir> <fin_sim>"""
import csv, sys
import numpy as np
gd, fin = sys.argv[1], float(sys.argv[2]); lo, hi = fin - 2.5, fin - 0.05
J = {}
for r in csv.DictReader(open(gd + "/joint.csv")):
    t = float(r["stamp"])
    if lo <= t <= hi: J.setdefault(r["name"], []).append((t, float(r["vel"])))
for n, s in sorted(J.items()):
    v = np.array([x[1] for x in s]); d = np.diff(v)
    alt = np.mean(np.sign(d[1:]) != np.sign(d[:-1]))
    fx = np.abs(np.fft.rfft(v - np.convolve(v, np.ones(25) / 25, "same"))); f = np.fft.rfftfreq(len(v), 0.002)
    print(n, "n", len(v), "dv/step sd", round(float(np.std(d)), 4), "sign-alt frac", round(float(alt), 3), "top Hz", [round(float(f[i]), 1) for i in np.argsort(fx)[-3:][::-1]])
I = [(float(r["stamp"]), float(r["ax"])) for r in csv.DictReader(open(gd + "/imu.csv")) if lo <= float(r["stamp"]) <= hi]
t = np.array([x[0] for x in I]); a = np.array([x[1] for x in I])
ph = np.round((t % 0.020) / 0.004).astype(int) % 5
print("IMU ax by 20 ms phase slot (mean, n):", [(k, round(float(a[ph == k].mean()), 3), int((ph == k).sum())) for k in range(5)])
ph2 = np.round((t % 0.008) / 0.004).astype(int) % 2
print("IMU ax by 8 ms parity:", [(k, round(float(a[ph2 == k].mean()), 3)) for k in range(2)], "overall", round(float(a.mean()), 3))
