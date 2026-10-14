import sys
from pyulog import ULog
u = ULog(sys.argv[1])
print("MAV_SYS_ID", u.initial_parameters.get("MAV_SYS_ID"), "start_us", u.start_timestamp, "dur_s", round((u.last_timestamp-u.start_timestamp)/1e6,1))
def ds(name):
    return [d for d in u.data_list if d.name == name]
t0 = int(u.start_timestamp)
def T(x):
    x = int(x)
    return None if x <= 0 else (x - t0) / 1e6   # 초기 timestamp 0 표본은 무효 (None) — unsigned 빼기 overflow 방지 (Codex 1557)
for d in ds("vehicle_command"):
    c = d.data
    for i in range(len(c["timestamp"])):
        if int(c["command"][i]) == 178:
            print("CMD178 t=%s p1=%.2f p2=%.2f p3=%.2f from_external=%s src_sys=%s" % (T(c["timestamp"][i]), c["param1"][i], c["param2"][i], c["param3"][i], c.get("from_external", [None]*99)[i], c["source_system"][i]))
for d in ds("vehicle_command_ack"):
    c = d.data
    for i in range(len(c["timestamp"])):
        if int(c["command"][i]) == 178:
            print("ACK178 t=%s result=%s" % (T(c["timestamp"][i]), c["result"][i]))
mr = ds("mission_result")
if mr:
    c = mr[0].data; last = None
    for i in range(len(c["timestamp"])):
        mid = int(c["mission_id"][i])
        if mid != last:
            print("MISSION_ID t=%s id=%d seq_total=%d finished=%d" % (T(c["timestamp"][i]), mid, c["seq_total"][i], c["finished"][i])); last = mid
    fin = [T(c["timestamp"][i]) for i in range(len(c["timestamp"])) if c["finished"][i]]
    print("first finished t", fin[:1])
pst = ds("position_setpoint_triplet")
if pst:
    c = pst[0].data; last = None
    for i in range(len(c["timestamp"])):
        v = round(float(c["current.cruising_speed"][i]), 2)
        if v != last:
            print("TRIPLET t=%s cruise=%.2f cur=(%.1f,%.1f)" % (T(c["timestamp"][i]), v, c["current.lat"][i]*1e0, c["current.lon"][i])); last = v
vs = ds("vehicle_status")
if vs:
    c = vs[0].data; last = None
    for i in range(len(c["timestamp"])):
        a = int(c["arming_state"][i])
        if a != last:
            print("ARMING t=%s state=%d" % (T(c["timestamp"][i]), a)); last = a
