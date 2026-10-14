"""GNSS 속도 융합 상태·ULog 안 Gazebo 실제값(groundtruth) 대조 (Codex 0455 2절). WSL python3. 사용: python3 ekf_fusion_dump.py <ulg> <out.json>
창 [fin−1, disarm+2]. estimator_aid_src_gnss_vel: fused·innovation_rejected·time_last_fuse·observation·innovation·observation_variance·test_ratio,
vehicle_local_position vs vehicle_local_position_groundtruth 수평 속도·위치 이동, estimator_states 가속도 bias(13~15, state.h 확인), EKF 인스턴스 수."""
import json, math, sys
from pyulog import ULog
u = ULog(sys.argv[1]); t0 = int(u.start_timestamp); T = lambda x: (int(x) - t0) / 1e6
def ds(n, m=0):
    d = [x for x in u.data_list if x.name == n and x.multi_id == m]; return d[0].data if d else None
mr = ds("mission_result"); ids = []
for k in range(len(mr["timestamp"])):
    i = int(mr["mission_id"][k])
    if i and (not ids or ids[-1] != i): ids.append(i)
fin = next(T(mr["timestamp"][k]) for k in range(len(mr["timestamp"])) if int(mr["mission_id"][k]) == ids[-1] and int(mr["finished"][k]))
vs = ds("vehicle_status")
dis = next(T(vs["timestamp"][i]) for i in range(1, len(vs["timestamp"])) if int(vs["arming_state"][i]) == 1 and int(vs["arming_state"][i - 1]) == 2 and T(vs["timestamp"][i]) >= fin - 1)
lo, hi = fin - 1.0, dis + 2.0
out = {"fin": round(fin, 3), "disarm": round(dis, 3), "ekf_instances": sorted({x.multi_id for x in u.data_list if x.name == "estimator_states"})}
g = ds("estimator_aid_src_gnss_vel")
if g:
    f = [k for k in g if k != "timestamp"]
    out["gnss_vel_fields"] = f
    sel = [i for i in range(len(g["timestamp"])) if lo <= T(g["timestamp"][i]) <= hi]
    def v(k, i): return float(g[k][i]) if k in g else None
    out["gnss_vel"] = [[round(T(g["timestamp"][i]) - fin, 3), v("fused", i), v("innovation_rejected", i), round((int(g["timestamp"][i]) - int(g["time_last_fuse"][i])) / 1e6, 3) if "time_last_fuse" in g else None,
                        round(v("observation[0]", i), 3), round(v("observation[1]", i), 3), round(v("innovation[0]", i), 3), round(v("innovation[1]", i), 3),
                        round(v("observation_variance[0]", i), 4), round(v("test_ratio[0]", i), 4)] for i in sel]
    out["gnss_vel_cols"] = ["t_rel", "fused", "rejected", "since_fuse_s", "obsN", "obsE", "innovN", "innovE", "obs_varN", "test_ratioN"]
lp, gt = ds("vehicle_local_position"), ds("vehicle_local_position_groundtruth")
def ser(d):
    return [(T(d["timestamp"][i]) - fin, float(d["x"][i]), float(d["y"][i]), math.hypot(float(d["vx"][i]), float(d["vy"][i]))) for i in range(len(d["timestamp"])) if lo <= T(d["timestamp"][i]) <= hi]
L, G = ser(lp), ser(gt) if gt else []
out["ekf_vs_truth"] = []
for t in [x / 10 for x in range(-10, int((hi - fin) * 10) + 1, 2)]:
    a = min(L, key=lambda r: abs(r[0] - t)); b = min(G, key=lambda r: abs(r[0] - t)) if G else None
    out["ekf_vs_truth"].append([round(t, 1), round(a[3], 3), None if b is None else round(b[3], 3)])
if G:
    g1 = [r for r in G if 1.0 <= r[0] <= dis - fin]; l1 = [r for r in L if 1.0 <= r[0] <= dis - fin]
    out["truth_move_after_fin1"] = round(max(math.hypot(r[1] - g1[0][1], r[2] - g1[0][2]) for r in g1), 4)
    out["ekf_move_after_fin1"] = round(max(math.hypot(r[1] - l1[0][1], r[2] - l1[0][2]) for r in l1), 4)
    out["truth_vmax_after_fin1"] = round(max(r[3] for r in g1), 4)
    # 실제 감속: groundtruth 수평 속도의 차분 (0.1 s 창) 최소 = 운동학 감속도
    acc = [((G[i][3] - G[i - 5][3]) / (G[i][0] - G[i - 5][0])) for i in range(5, len(G)) if -1.0 <= G[i][0] <= 1.0 and G[i][0] - G[i - 5][0] > 0]
    out["truth_decel_min_mps2"] = round(min(acc), 3) if acc else None
    out["truth_v_at_fin_minus"] = [[round(r[0], 2), round(r[3], 3)] for r in G if -1.0 <= r[0] <= 0.6][::4]
es = ds("estimator_states")
out["accel_bias"] = [[round(T(es["timestamp"][i]) - fin, 2)] + [round(float(es[f"states[{k}]"][i]), 4) for k in (13, 14, 15)] for i in range(len(es["timestamp"])) if lo <= T(es["timestamp"][i]) <= hi][::5]
json.dump(out, open(sys.argv[2], "w"))
print("fin", out["fin"], "inst", out["ekf_instances"], "truth move", out.get("truth_move_after_fin1"), "ekf move", out.get("ekf_move_after_fin1"), "truth vmax", out.get("truth_vmax_after_fin1"), "truth decel", out.get("truth_decel_min_mps2"), "gnss fields", out.get("gnss_vel_fields", [])[:12])
