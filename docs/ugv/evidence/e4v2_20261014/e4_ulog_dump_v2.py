"""E4 ULog 덤프 (WSL python3 + pyulog). 사용: python3 e4_ulog_dump.py <ulg> <out.json>
판정에 필요한 것만: 파라미터, 주 미션의 seq_reached 순서, finished 시각, finished 뒤 첫 speed setpoint 0, disarm 시각, 지역 위치 속도 계열(정렬용)."""
import json
import math
import sys

from pyulog import ULog

u = ULog(sys.argv[1]); t0 = int(u.start_timestamp)
T = lambda x: round((int(x) - t0) / 1e6, 4)
P = u.initial_parameters
def ds(n):
    d = [x for x in u.data_list if x.name == n]; return d[0].data if d else None
out = {"ulg": sys.argv[1], "params": {k: P.get(k) for k in ("MAV_SYS_ID", "NAV_ACC_RAD", "RA_ACC_RAD_MAX")}}
mr = ds("mission_result")
ids = sorted(set(int(x) for x in mr["mission_id"]))
main = max(ids, key=lambda i: max(int(mr["seq_total"][k]) for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == i))
seq = []
for k in range(len(mr["timestamp"])):
    if int(mr["mission_id"][k]) == main:
        s = int(mr["seq_reached"][k])
        if not seq or seq[-1] != s:
            seq.append(s)
tot = max(int(mr["seq_total"][k]) for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == main)
fin = next((T(mr["timestamp"][k]) for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == main and int(mr["finished"][k])), None)
out.update(main_mission=main, seq_total=tot, seq_reached=seq, finished_t=fin)
rs = ds("rover_speed_setpoint")
if rs and fin is not None:
    key = "speed_body_x" if "speed_body_x" in rs else [k for k in rs if "speed" in k][0]
    # v2 (Codex 0130 P4): 과거의 0 을 집지 않게 [fin − 0.5, fin + 2] 안에서, 그 뒤 fin + 0.1 까지 0 이 계속되는 첫 표본만
    ts = [(T(rs["timestamp"][i]), abs(float(rs[key][i])) < 1e-3) for i in range(len(rs["timestamp"]))]
    sp0 = None
    for i, (t, z) in enumerate(ts):
        if fin - 0.5 <= t <= fin + 2.0 and z and all(zz for tt, zz in ts[i:] if tt <= fin + 0.1):
            sp0 = t; break
    out["speed_sp_zero_after_finished_t"] = sp0
    out["speed_sp_zero_rule"] = "v2: [fin-0.5, fin+2] 첫 0, fin+0.1 까지 연속 0"
vs = ds("vehicle_status")
arm = [(T(vs["timestamp"][i]), int(vs["arming_state"][i])) for i in range(len(vs["timestamp"]))]
out["disarm_t"] = next((arm[i][0] for i in range(1, len(arm)) if arm[i][1] == 1 and arm[i - 1][1] == 2 and (fin is None or arm[i][0] >= fin)), None)
vc = ds("vehicle_command")
out["cmd400_t"] = [T(vc["timestamp"][i]) for i in range(len(vc["timestamp"])) if int(vc["command"][i]) == 400 and (fin is None or T(vc["timestamp"][i]) >= fin - 1)] if vc else []
lp = ds("vehicle_local_position")
out["speed_series"] = [[T(lp["timestamp"][i]), round(math.hypot(float(lp["vx"][i]), float(lp["vy"][i])), 3)] for i in range(0, len(lp["timestamp"]), 2)]
pcs = ds("position_controller_status")
out["acceptance_radius_values"] = sorted(set(round(float(x), 2) for x in pcs["acceptance_radius"])) if pcs else None
json.dump(out, open(sys.argv[2], "w"))
print("ok", out["params"], "seq", len(seq), "/", tot, "fin", fin, "sp0", out.get("speed_sp_zero_after_finished_t"), "disarm", out["disarm_t"])
