"""경사 정지 반복 (Fable 3절) ULog 덤프 — WSL python3 + pyulog. 사용: python3 slope_ulog_dump.py <ulg> <out.json>
정지 미션 = 마지막 mission_id. 기록: 미션 목록(id·처음 시각·finished 시각·seq_total), 트리플릿 cruise 변화, CMD178(속도 변경),
정지 미션 finished 뒤 speed setpoint 0 (E4 v2 규칙: [fin−0.5, fin+2] 첫 0, fin+0.1 까지 연속), disarm, 지역 위치 속도 계열."""
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
mis = {}
for k in range(len(mr["timestamp"])):
    i = int(mr["mission_id"][k]); t = T(mr["timestamp"][k])
    m = mis.setdefault(i, {"id": i, "first_t": t, "finished_t": None, "seq_total": int(mr["seq_total"][k]), "seq": []})
    if int(mr["finished"][k]) and m["finished_t"] is None:
        m["finished_t"] = t
    s = int(mr["seq_reached"][k])
    if not m["seq"] or m["seq"][-1] != s:
        m["seq"].append(s)
ml = sorted((m for m in mis.values() if m["id"] != 0), key=lambda m: m["first_t"])
out["missions"] = ml
stop = ml[-1] if ml else None
out["stop_mission"] = stop
pst = ds("position_setpoint_triplet")
cr, last = [], None
for i in range(len(pst["timestamp"])):
    v = round(float(pst["current.cruising_speed"][i]), 3)
    if v != last:
        cr.append([T(pst["timestamp"][i]), v]); last = v
out["triplet_cruise_changes"] = cr
vc = ds("vehicle_command")
out["cmd178"] = [[T(vc["timestamp"][i]), round(float(vc["param2"][i]), 3), int(vc["from_external"][i])]
                 for i in range(len(vc["timestamp"])) if int(vc["command"][i]) == 178] if vc else []
out["cmd400_t"] = [T(vc["timestamp"][i]) for i in range(len(vc["timestamp"])) if int(vc["command"][i]) == 400] if vc else []
fin = stop["finished_t"] if stop else None
rs = ds("rover_speed_setpoint")
if rs and fin is not None:
    key = "speed_body_x" if "speed_body_x" in rs else [k for k in rs if "speed" in k][0]
    ts = [(T(rs["timestamp"][i]), abs(float(rs[key][i])) < 1e-3) for i in range(len(rs["timestamp"]))]
    out["speed_sp_zero_after_finished_t"] = next((t for j, (t, z) in enumerate(ts) if fin - 0.5 <= t <= fin + 2.0 and z
                                                  and all(zz for tt, zz in ts[j:] if tt <= fin + 0.1)), None)
vs = ds("vehicle_status")
arm = [(T(vs["timestamp"][i]), int(vs["arming_state"][i])) for i in range(len(vs["timestamp"]))]
out["disarm_t"] = next((arm[i][0] for i in range(1, len(arm)) if arm[i][1] == 1 and arm[i - 1][1] == 2 and (fin is None or arm[i][0] >= fin - 1)), None)
lp = ds("vehicle_local_position")
out["speed_series"] = [[T(lp["timestamp"][i]), round(math.hypot(float(lp["vx"][i]), float(lp["vy"][i])), 3)] for i in range(0, len(lp["timestamp"]), 2)]
json.dump(out, open(sys.argv[2], "w"))
print("ok", out["params"], "missions", [(m["id"] % 100000, m["first_t"], m["finished_t"]) for m in ml][-3:], "cruise", cr[-4:], "sp0", out.get("speed_sp_zero_after_finished_t"), "disarm", out["disarm_t"])
