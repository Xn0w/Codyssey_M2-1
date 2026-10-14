"""E3 끝 지점 정지 기전 (Codex 1705 ②): 마지막 목표·도착 속도·반경·속도 설정 0·위치를 같은 ULog 시간축으로."""
import sys, math
from pyulog import ULog
u = ULog(sys.argv[1]); t0 = int(u.start_timestamp)
def T(x): return (int(x) - t0) / 1e6
def ds(n):
    d = [x for x in u.data_list if x.name == n]; return d[0].data if d else None
mr = ds("mission_result"); fin = next(T(mr["timestamp"][i]) for i in range(len(mr["timestamp"])) if mr["finished"][i] and T(mr["timestamp"][i]) > 5)
rps = ds("rover_position_setpoint"); rss = ds("rover_speed_setpoint"); lp = ds("vehicle_local_position"); pcs = ds("position_controller_status")
print("fields rover_position_setpoint:", [k for k in rps if k != "timestamp"][:12] if rps else None)
def at(d, t, key):
    i = min(range(len(d["timestamp"])), key=lambda k: abs(T(d["timestamp"][k]) - t)); return d[key][i], T(d["timestamp"][i])
z0 = next((T(rss["timestamp"][i]) for i in range(len(rss["timestamp"])) if T(rss["timestamp"][i]) > fin - 15 and abs(float(rss["speed_body_x"][i])) < 1e-3), None)
print("finished %.3f  first speed setpoint 0 at %s" % (fin, z0))
if rps:
    keys = [k for k in rps if k.startswith("position_ned") or k in ("arrival_speed", "cruising_speed")]
    for t in [z0 - 1.0, z0 - 0.2, z0, fin, z0 + 2.0]:
        if t is None: continue
        tx, _ = at(rps, t, "position_ned[0]"); ty, _ = at(rps, t, "position_ned[1]"); arr, _ = at(rps, t, "arrival_speed")
        x, tt = at(lp, t, "x"); y, _ = at(lp, t, "y"); vx, _ = at(lp, t, "vx"); vy, _ = at(lp, t, "vy")
        print("t %.3f  target (%.2f, %.2f) arrival %.2f | pos (%.2f, %.2f) dist %.2f m speed %.2f" % (tt, tx, ty, arr, x, y, math.hypot(tx - x, ty - y), math.hypot(vx, vy)))
    xe, _ = at(lp, T(lp["timestamp"][-1]), "x"); ye, _ = at(lp, T(lp["timestamp"][-1]), "y")
    txe, _ = at(rps, z0, "position_ned[0]"); tye, _ = at(rps, z0, "position_ned[1]")
    print("final pos (%.2f, %.2f) → target dist %.2f m" % (xe, ye, math.hypot(txe - xe, tye - ye)))
if pcs: print("acceptance_radius values", sorted(set(round(float(x), 2) for x in pcs["acceptance_radius"])))
