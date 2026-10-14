import sys
from pyulog import ULog
u = ULog(sys.argv[1]); t0 = int(u.start_timestamp)
P = u.initial_parameters
def ds(n): return [d for d in u.data_list if d.name == n]
mr = ds("mission_result")[0].data
ids = sorted(set(int(x) for x in mr["mission_id"]))
main = max(ids, key=lambda i: max(int(mr["seq_total"][k]) for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == i))
seqs = [int(mr["seq_reached"][k]) for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == main]
tot = max(int(mr["seq_total"][k]) for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == main)
uniq = []
for x in seqs:
    if not uniq or x != uniq[-1]: uniq.append(x)
pcs = ds("position_controller_status")
print("SYS", P.get("MAV_SYS_ID"), "NAV_ACC_RAD", P.get("NAV_ACC_RAD"), "RA_ACC_RAD_MAX", P.get("RA_ACC_RAD_MAX"), "| mission", main, "seq_total", tot, "seq_reached sequence", uniq,
      "| pos_ctrl_status", 0 if not pcs else len(pcs[0].data["timestamp"]), sorted(set(round(float(x), 2) for x in pcs[0].data["acceptance_radius"])) if pcs else None)
