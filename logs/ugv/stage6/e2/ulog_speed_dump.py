import sys, math
from pyulog import ULog
u = ULog(sys.argv[1]); t0 = int(u.start_timestamp)
lp = [d for d in u.data_list if d.name == "vehicle_local_position"][0].data
vs = [d for d in u.data_list if d.name == "vehicle_status"][0].data
with open(sys.argv[2], "w") as f:
    f.write("t_ulog,v\n")
    for i in range(len(lp["timestamp"])):
        if int(lp["timestamp"][i]) > 0:
            f.write("%.4f,%.4f\n" % ((int(lp["timestamp"][i]) - t0) / 1e6, math.hypot(float(lp["vx"][i]), float(lp["vy"][i]))))
print("start_utc_us", u.start_timestamp)
