"""IMU 표본 격자(250 Hz = 물리 2 ms 스텝의 격 스텝) 와 액추에이터 명령(actuator_motors) 시각의 위상 대조 (WSL pyulog, 읽기 전용).
사용: python3 imu_phase.py <ulg> <label> <lo_rel_fin> <hi_rel_fin>
각 IMU 표본(sensor_combined)에 대해 '직전 actuator_motors 발행 뒤 경과(ms)' 를 2 ms 격자로 묶어 표본 가속도 x 의 평균·개수를 낸다 → 임펄스가 명령 뒤 몇 스텝에 걸리고 IMU 가 그것을 매 주기 잡는지.
"""
import math, sys
from collections import defaultdict
from pyulog import ULog

u = ULog(sys.argv[1]); label = sys.argv[2]; lo_r, hi_r = float(sys.argv[3]), float(sys.argv[4])
t0 = int(u.start_timestamp); T = lambda x: (int(x) - t0) / 1e6
def ds(n, m=0):
    d = [x for x in u.data_list if x.name == n and x.multi_id == m]; return d[0].data if d else None
mr = ds("mission_result"); ids = []
for k in range(len(mr["timestamp"])):
    i = int(mr["mission_id"][k])
    if i and (not ids or ids[-1] != i): ids.append(i)
fin = next((T(mr["timestamp"][k]) for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == ids[-1] and int(mr["finished"][k])), None)
lo, hi = fin + lo_r, fin + hi_r
sc = ds("sensor_combined"); am = ds("actuator_motors"); ao = ds("actuator_outputs"); rs = ds("rover_speed_setpoint"); wh = ds("rover_throttle_setpoint")
def win(d):
    return [i for i in range(len(d["timestamp"])) if lo <= T(d["timestamp"][i]) <= hi]
si = win(sc)
ts_imu = [T(sc["timestamp"][i]) for i in si]
ax = [float(sc["accelerometer_m_s2[0]"][i]) for i in si]
# IMU sample grid phase: timestamps modulo 4 ms (sim time in us) -> which 2 ms step parity
par = defaultdict(int)
for i in si: par[int(sc["timestamp"][i]) % 4000] += 1
print(f"{label}: window [{lo:.2f},{hi:.2f}] IMU n={len(si)} timestamp%4000us histogram {dict(par)}")
for name, d in (("actuator_motors", am), ("actuator_outputs", ao), ("rover_throttle_setpoint", wh), ("rover_speed_setpoint", rs)):
    if d is None: print(" ", name, "absent"); continue
    wi = win(d); ts = [T(d["timestamp"][i]) for i in wi]
    if len(ts) < 3: print(" ", name, "n", len(ts)); continue
    dts = sorted(ts[k + 1] - ts[k] for k in range(len(ts) - 1))
    ph = defaultdict(int)
    for i in wi: ph[int(d["timestamp"][i]) % 4000] += 1
    print(f"  {name}: n={len(ts)} dt med {dts[len(dts)//2]*1000:.2f} ms p99 {dts[int(0.99*(len(dts)-1))]*1000:.2f} | timestamp%4000us {dict(ph)}")
    if name == "actuator_motors":
        # for each IMU sample, elapsed since the last actuator_motors timestamp, binned 2 ms
        tsa = sorted(ts); j = 0; bins = defaultdict(list)
        for t, a in zip(ts_imu, ax):
            while j + 1 < len(tsa) and tsa[j + 1] <= t: j += 1
            if tsa[j] <= t:
                el = round((t - tsa[j]) * 1000 / 2) * 2
                bins[el].append(a)
        print("  accel_x by elapsed-since-last-actuator_motors (ms): " + ", ".join(f"{k}ms:n={len(v)},mean={sum(v)/len(v):.2f}" for k, v in sorted(bins.items()) if k <= 24))
        # also actuator value change magnitude per message (control[0])
        key = "control[0]" if "control[0]" in d else None
        if key:
            vals = [float(d[key][i]) for i in wi]
            dv = [abs(vals[k + 1] - vals[k]) for k in range(len(vals) - 1)]
            print(f"  actuator_motors control[0] mean {sum(vals)/len(vals):.3f} mean|step| {sum(dv)/len(dv):.4f} max|step| {max(dv):.4f}")
# run-level: low-group timing — fraction of 'low' (< -2.5) samples by timestamp%20000us (50 Hz phase)
ph50 = defaultdict(lambda: [0, 0])
for i in si:
    k = int(sc["timestamp"][i]) % 20000; ph50[k][1] += 1
    if float(sc["accelerometer_m_s2[0]"][i]) < -2.5: ph50[k][0] += 1
print("  low-sample fraction by timestamp%20ms: " + ", ".join(f"{k/1000:.0f}ms:{a}/{b}" for k, (a, b) in sorted(ph50.items())))
