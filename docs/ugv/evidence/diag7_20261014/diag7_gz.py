"""진단 7 gz↔PX4 단계 대조 (WSL python3 + pyulog + numpy). 사용: python3 diag7_gz.py <ulg> <gzrec_dir> <out.json>
1) 브리지 보존: gz IMU (FLU, sim stamp) 와 PX4 sensor_accel (FRD, hrt) 를 표본 단위로 맞춤 — x 같음, y·z 부호 반대 가정을 값 상관으로 검증,
   hrt − sim stamp 오프셋을 정확 일치(최소 오차)로 찾고 일치율·최대 차를 기록.
2) gz 센서 vs gz 운동: 창 W1=[fin−2.5, fin−0.05] (fin 은 ULog mission_result, 위 오프셋으로 sim 시각 변환) 에서
   gz IMU (자체 자세 q 로 세계 회전, 중력 9.8 보정) 적분 진행 방향 Δv  vs  gz pose 위치 차분 속도의 Δv (같은 sim stamp 구간).
   pose 표본률(≈ 55 Hz)로는 50 Hz 가속도를 복원할 수 없다 — Δv(누적) 비교만, 주파수 원천은 미확인.
3) 명령: cmd.csv (Actuators header stamp 가 0 이면 wall 시각만), joint.csv 바퀴 속도 주기·W1 평균.
4) 실제 토픽 주기: 각 CSV 의 stamp/wall 차분 중앙값·최대."""
import csv, json, math, sys
import numpy as np
from pyulog import ULog

ulg, gd, outp = sys.argv[1], sys.argv[2], sys.argv[3]
u = ULog(ulg); t0 = int(u.start_timestamp)
def ds(n, m=0):
    d = [x for x in u.data_list if x.name == n and x.multi_id == m]; return d[0].data if d else None
def rd(name):
    with open(f"{gd}/{name}.csv") as f:
        return list(csv.DictReader(f))
out = {"ulg": ulg, "gzrec": gd}
gi = rd("imu"); gp = rd("pose"); gj = rd("joint"); gc = rd("cmd")
gs = np.array([float(r["stamp"]) for r in gi]); gax = np.array([float(r["ax"]) for r in gi]); gay = np.array([float(r["ay"]) for r in gi]); gaz = np.array([float(r["az"]) for r in gi])
sa = ds("sensor_accel"); ht = np.array(sa["timestamp_sample"], dtype=float) * 1e-6; px = np.array(sa["x"], float); py = np.array(sa["y"], float); pz = np.array(sa["z"], float)
def per(a):
    d = np.diff(a); return {"median_ms": round(float(np.median(d)) * 1e3, 3), "max_ms": round(float(np.max(d)) * 1e3, 3), "n": int(len(a)), "monotonic": bool(np.all(d > 0))}
out["rates"] = {"gz_imu": per(gs), "gz_pose": per(np.array([float(r["stamp"]) for r in gp])), "gz_joint_msgs": per(np.unique([float(r["stamp"]) for r in gj])),
                "gz_cmd_wall": per(np.array([float(r["wall"]) for r in gc])), "px4_sensor_accel": per(ht)}
out["cmd_stamp_zero_frac"] = round(sum(1 for r in gc if float(r["stamp"]) == 0.0) / max(1, len(gc)), 3)
# 1) 오프셋: 4 ms 격자 키로 정확 일치 탐색 (offset_probe.py 와 같은 방법; 진단 7 평지 b 에서 hrt == sim stamp, 오프셋 0 확인)
gk = np.round(gs / 0.004).astype(np.int64); hk = np.round(ht / 0.004).astype(np.int64)
gidx = {int(k): i for i, k in enumerate(gk)}
best = None
for lag in range(-50000, 50001, 1):
    keys = hk[::50] - lag
    pairs = [(gidx.get(int(k)), j) for k, j in zip(keys, range(0, len(hk), 50))]
    pairs = [(i, j) for i, j in pairs if i is not None]
    if len(pairs) < 100: continue
    e = float(np.median([abs(gax[i] - px[j]) for i, j in pairs]))
    if best is None or e < best[0]: best = (e, lag)
    if e < 1e-5: break
off = None
if best:
    lag = best[1]; off = lag * 0.004
    pairs = [(gidx.get(int(k)), j) for j, k in enumerate(hk - lag)]
    pairs = [(i, j) for i, j in pairs if i is not None]
    ex = np.array([abs(gax[i] - px[j]) for i, j in pairs]); ey = np.array([abs(-gay[i] - py[j]) for i, j in pairs]); ez = np.array([abs(-gaz[i] - pz[j]) for i, j in pairs])
    out["bridge"] = {"offset_hrt_minus_sim_s": round(off, 6), "matched_px4_frac": round(len(pairs) / len(hk), 4),
                     "abs_err_x_max": float(ex.max()), "abs_err_y_max": float(ey.max()), "abs_err_z_max": float(ez.max()),
                     "frac_exact_xyz_1e-4": round(float(np.mean((ex < 1e-4) & (ey < 1e-4) & (ez < 1e-4))), 4),
                     "frame_assumed": "PX4 FRD x = gz x, y = −gz y, z = −gz z", "method": "4 ms 격자 키 정확 일치"}
# fin
mr = ds("mission_result"); ids = []
for k in range(len(mr["timestamp"])):
    i = int(mr["mission_id"][k])
    if i and (not ids or ids[-1] != i): ids.append(i)
fin_h = next(int(mr["timestamp"][k]) * 1e-6 for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == ids[-1] and int(mr["finished"][k]))
out["fin_hrt_s"] = round(fin_h, 3)
if off is not None:
    fin_s = fin_h - off; lo, hi = fin_s - 2.5, fin_s - 0.05
    out["fin_sim_s"] = round(fin_s, 3)
    # gz pose 속도 (위치 차분, 같은 sim stamp)
    ps = np.array([float(r["stamp"]) for r in gp]); X = np.array([float(r["x"]) for r in gp]); Y = np.array([float(r["y"]) for r in gp])
    u_ = np.searchsorted(ps, fin_s - 1.0)
    vx = (X[u_ + 1] - X[u_ - 1]) / (ps[u_ + 1] - ps[u_ - 1]); vy = (Y[u_ + 1] - Y[u_ - 1]) / (ps[u_ + 1] - ps[u_ - 1]); nrm = math.hypot(vx, vy)
    ux, uy = vx / nrm, vy / nrm                                          # 진행 방향 (gz 세계 ENU)
    def vel_at(t):
        k = np.searchsorted(ps, t); k = min(max(k, 1), len(ps) - 2)
        return ((X[k + 1] - X[k - 1]) * ux + (Y[k + 1] - Y[k - 1]) * uy) / (ps[k + 1] - ps[k - 1])
    dv_pose = vel_at(hi) - vel_at(lo)
    # gz IMU 세계 회전 적분 (자체 q, ENU), 중력 (0,0,9.8) 빼기
    qw = np.array([float(r["qw"]) for r in gi]); qx = np.array([float(r["qx"]) for r in gi]); qy = np.array([float(r["qy"]) for r in gi]); qz = np.array([float(r["qz"]) for r in gi])
    sel = np.where((gs >= lo) & (gs <= hi))[0]
    dv = 0.0
    for i in sel:
        w, x, y, z = qw[i], qx[i], qy[i], qz[i]
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
        a = R @ np.array([gax[i], gay[i], gaz[i]]) - np.array([0, 0, 9.8])
        dt = gs[i + 1] - gs[i] if i + 1 < len(gs) else 0.004
        dv += (a[0] * ux + a[1] * uy) * dt
    out["gz_W1"] = {"window_sim": [round(lo, 3), round(hi, 3)], "dv_imu_world_fwd": round(dv, 4), "dv_pose_diff_fwd": round(dv_pose, 4),
                    "E_gz_imu_minus_gz_pose": round(dv - dv_pose, 4), "n_imu": int(len(sel)), "pose_rate_note": "pose ≈ 55 Hz 차분 — 누적 Δv 비교만",
                    "imu_q_source": "gz IMU orientation 필드 (센서 기준 자세)"}
    # 정지 창 기준선 (W2 상당 fin+0.8 ~ fin+2.5): gz IMU 세계 가속 평균 (정지면 0)
    sel2 = np.where((gs >= fin_s + 0.8) & (gs <= fin_s + 2.5))[0]
    acc2 = []
    for i in sel2:
        w, x, y, z = qw[i], qx[i], qy[i], qz[i]
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
        a = R @ np.array([gax[i], gay[i], gaz[i]]) - np.array([0, 0, 9.8]); acc2.append(a[0] * ux + a[1] * uy)
    out["gz_static_fwd_acc_mean"] = round(float(np.mean(acc2)), 4) if acc2 else None
    # 바퀴 속도 W1 평균·명령 주기
    jw = [(float(r["stamp"]), float(r["vel"])) for r in gj if lo <= float(r["stamp"]) <= hi]
    out["wheel_vel_W1_mean"] = round(float(np.mean([v for _, v in jw])), 3) if jw else None
json.dump(out, open(outp, "w"), indent=1)
print(json.dumps({k: out.get(k) for k in ("rates", "cmd_stamp_zero_frac", "bridge", "gz_W1", "gz_static_fwd_acc_mean")}, ensure_ascii=False))
