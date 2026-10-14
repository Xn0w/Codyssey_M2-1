"""진행 방향 부호 속도: EKF·GNSS 관측·groundtruth 를 정지 전 실제 진행 방향 단위벡터에 투영. 사용: python3 ekf_signed.py <ulg>"""
import math, sys
from pyulog import ULog
u = ULog(sys.argv[1]); t0 = int(u.start_timestamp); T = lambda x: (int(x) - t0) / 1e6
P = u.initial_parameters
def ds(n, m=0):
    d = [x for x in u.data_list if x.name == n and x.multi_id == m]; return d[0].data if d else None
mr = ds("mission_result"); ids = []
for k in range(len(mr["timestamp"])):
    i = int(mr["mission_id"][k])
    if i and (not ids or ids[-1] != i): ids.append(i)
fin = next(T(mr["timestamp"][k]) for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == ids[-1] and int(mr["finished"][k]))
gt, lp, g = ds("vehicle_local_position_groundtruth"), ds("vehicle_local_position"), ds("estimator_aid_src_gnss_vel")
i0 = min(range(len(gt["timestamp"])), key=lambda i: abs(T(gt["timestamp"][i]) - (fin - 1.0)))
ux, uy = float(gt["vx"][i0]), float(gt["vy"][i0]); n = math.hypot(ux, uy); ux, uy = ux / n, uy / n
def at(d, kx, ky, t):
    i = min(range(len(d["timestamp"])), key=lambda j: abs(T(d["timestamp"][j]) - t)); return float(d[kx][i]) * ux + float(d[ky][i]) * uy
print("params", {k: P.get(k) for k in ("EKF2_GPS_DELAY", "EKF2_IMU_POS_X", "SIM_GPS_USED", "EKF2_GPS_V_NOISE", "EKF2_ACC_NOISE", "EKF2_GYR_NOISE", "EKF2_ACC_B_NOISE")})
print("t_rel  truth  ekf  gnss_obs")
for k in ([int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else range(-12, 31, 2)):
    t = fin + k / 10
    print(f"{k/10:5.1f} {at(gt,'vx','vy',t):6.3f} {at(lp,'vx','vy',t):6.3f} {at(g,'observation[0]','observation[1]',t):6.3f}")
# GNSS 관측 지연 추정: truth 와 GNSS 관측 시계열의 상호 상관 최대 지연 (감속 구간)
ts = [fin - 2 + j * 0.02 for j in range(150)]
tr = [at(gt, 'vx', 'vy', t) for t in ts]
best = None
for lag in [x / 50 for x in range(-60, 61)]:
    e = sum((at(g, 'observation[0]', 'observation[1]', t) - at(gt, 'vx', 'vy', t - lag)) ** 2 for t in ts[::3])
    best = (e, lag) if best is None or e < best[0] else best
print("GNSS obs vs truth best lag (obs(t) ≈ truth(t − lag))", best[1], "rss", round(best[0], 3))
best = None
for lag in [x / 50 for x in range(-60, 61)]:
    e = sum((at(lp, 'vx', 'vy', t) - at(gt, 'vx', 'vy', t - lag)) ** 2 for t in ts[::3] if t < fin)
    best = (e, lag) if best is None or e < best[0] else best
print("EKF vs truth best lag (before fin)", best[1], "rss", round(best[0], 3))
