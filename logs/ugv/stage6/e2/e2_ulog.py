import sys
from pyulog import ULog
u = ULog(sys.argv[1]); t0 = int(u.start_timestamp)
def T(x):
    x = int(x); return None if x <= 0 else round((x - t0) / 1e6, 3)
P = u.initial_parameters
print("MAV_SYS_ID", P.get("MAV_SYS_ID"), "NAV_ACC_RAD", P.get("NAV_ACC_RAD"), "RA_ACC_RAD_MAX", P.get("RA_ACC_RAD_MAX"), "dur", round((u.last_timestamp - u.start_timestamp) / 1e6, 1))
def ds(n): return [d for d in u.data_list if d.name == n]
for d in ds("vehicle_command"):
    c = d.data
    for i in range(len(c["timestamp"])):
        if int(c["command"][i]) == 178: print("CMD178", T(c["timestamp"][i]), round(float(c["param2"][i]), 2), "ext", c["from_external"][i])
mr = ds("mission_result")
if mr:
    c = mr[0].data; last = None
    for i in range(len(c["timestamp"])):
        k = (int(c["mission_id"][i]), int(c["finished"][i]))
        if k != last: print("MISSION", T(c["timestamp"][i]), "id", k[0], "finished", k[1], "seq_total", c["seq_total"][i]); last = k
pcs = ds("position_controller_status")
print("position_controller_status msgs", 0 if not pcs else len(pcs[0].data["timestamp"]), "acc_rad values", sorted(set(round(float(x), 2) for x in pcs[0].data["acceptance_radius"])) if pcs else None)
pst = ds("position_setpoint_triplet")
if pst:
    c = pst[0].data; last = None
    for i in range(len(c["timestamp"])):
        v = round(float(c["current.cruising_speed"][i]), 2)
        if v != last: print("TRIPLET", T(c["timestamp"][i]), "cruise", v); last = v
rs = ds("rover_speed_setpoint")
if rs:
    c = rs[0].data; key = [k for k in c if "speed" in k and k != "timestamp"][0]
    first0 = next((T(c["timestamp"][i]) for i in range(len(c["timestamp"])) if T(c["timestamp"][i]) and T(c["timestamp"][i]) > 30 and abs(float(c[key][i])) < 1e-3), None)
    print("rover_speed_setpoint field", key, "first zero after 30s", first0)
vs = ds("vehicle_status")
if vs:
    c = vs[0].data; last = None
    for i in range(len(c["timestamp"])):
        a = int(c["arming_state"][i])
        if a != last: print("ARMING", T(c["timestamp"][i]), a); last = a
lp = ds("vehicle_local_position")
if lp:
    c = lp[0].data
    import math
    sp = [(T(c["timestamp"][i]), math.hypot(float(c["vx"][i]), float(c["vy"][i]))) for i in range(len(c["timestamp"]))]
    # 저속 연속 구간 (Codex 1645 정정): 실제 표본으로 지속시간 ≥ 1 s, 유한값, 표본 공백 ≤ 0.2 s, disarm 이전에 1 s 를 채웠는지
    disarm = None
    if vs:
        c2 = vs[0].data
        disarm = next((T(c2["timestamp"][i]) for i in range(1, len(c2["timestamp"])) if int(c2["arming_state"][i]) == 1 and int(c2["arming_state"][i - 1]) == 2), None)
    runs, cur = [], None
    for t, v in sp:
        ok = t is not None and v == v and v < 0.2 and t > 30
        if ok and cur is not None and t - cur[1] <= 0.2:
            cur[1] = t
        elif ok:
            if cur: runs.append(cur)
            cur = [t, t]
        else:
            if cur: runs.append(cur); cur = None
    if cur: runs.append(cur)
    print("disarm", disarm)
    for a0, a1 in runs:
        print("slow run %.3f ~ %.3f (%.3f s) | before disarm: %s s" % (a0, a1, a1 - a0, None if disarm is None else round(min(a1, disarm) - a0, 3)))
