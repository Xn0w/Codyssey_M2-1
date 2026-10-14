"""500 Hz 적용 확인 (WSL pyulog). 사용: python3 imu_rate_check.py <ulg> <out.json>"""
import json, sys
import numpy as np
from pyulog import ULog
u = ULog(sys.argv[1], ["vehicle_imu_status", "vehicle_imu"])
s = [x for x in u.data_list if x.name == "vehicle_imu_status" and x.multi_id == 0][0].data
v = [x for x in u.data_list if x.name == "vehicle_imu" and x.multi_id == 0][0].data
out = {"accel_rate_hz_median": float(np.median(s["accel_rate_hz"])), "dv_dt_us_median": float(np.median(v["delta_velocity_dt"])),
       "dv_clip_values": sorted(set(np.array(v["delta_velocity_clipping"]).astype(int).tolist()))}
json.dump(out, open(sys.argv[2], "w")); print(out)
