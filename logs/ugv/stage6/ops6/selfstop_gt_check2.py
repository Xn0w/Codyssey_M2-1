"""운영 park 1.0 s 회차의 '차단 전 자체 정지' 재분석 (Codex 0806 2절, 새 Gazebo 없음, WSL python3 + pyulog).
같은 PX4 시계로: vehicle_local_position_groundtruth (Gazebo 진실 위치/속도, timestamp_sample) 수평 속도,
vehicle_command 400 (disarm 요청, param1=0) 시각, actuator_armed 해제 시각, actuator_outputs 변화 시각, mission_result finished.
보수적 하한: 저속 시작 = '마지막 ≥ 0.2 표본 뒤 첫 < 0.2 표본' 시각 (실제 교차는 그 이전일 수 있음 → 하한), 차단 경계 = 가장 이른 (disarm 요청, armed 해제, 출력 변화).
사용: python3 selfstop_gt_check.py <ulg> <out.json>"""
import json, sys
import numpy as np
from pyulog import ULog
u = ULog(sys.argv[1]); D = {(d.name, d.multi_id): d for d in u.data_list}
g = D[("vehicle_local_position_groundtruth", 0)].data
ts = (g["timestamp_sample"] if "timestamp_sample" in g else g["timestamp"]) / 1e6; tpub = g["timestamp"] / 1e6
v = np.hypot(g["vx"], g["vy"])
c = D[("vehicle_command", 0)].data
dis_req = [t / 1e6 for t, cm, p in zip(c["timestamp"], c["command"], c["param1"]) if int(cm) == 400 and p == 0.0]
a = D[("actuator_armed", 0)].data; ar = a["armed"].astype(int)
unarm = [a["timestamp"][k + 1] / 1e6 for k in np.where(np.diff(ar) == -1)[0]]
mr = D[("mission_result", 0)].data; fin = [t / 1e6 for t, f in zip(mr["timestamp"], mr["finished"]) if f]
cut_candidates = {"disarm_request": dis_req[-1] if dis_req else None, "armed_false": unarm[-1] if unarm else None}
# actuator_outputs: 차단 직전 마지막 출력값과 달라지는 첫 시각 (disarm 요청 −2 s 이후)
for key in [k for k in D if k[0] == "actuator_outputs"]:
    o = D[key].data; ot = o["timestamp"] / 1e6; ref = cut_candidates["disarm_request"]
    if ref is None: continue
    cols = [k for k in o if k.startswith("output[")][:4]
    m = np.column_stack([o[k] for k in cols]); i0 = int(np.searchsorted(ot, ref - 2.0)); base = m[i0]
    ch = [ot[i] for i in range(i0 + 1, len(ot)) if np.any(np.abs(m[i] - base) > 1e-3)]
    cut_candidates[f"actuator_outputs_{key[1]}_first_change_after_ref-2s"] = ch[0] if ch else None
cut = min(t for t in [cut_candidates["disarm_request"], cut_candidates["armed_false"]] if t is not None)
pre = np.where(ts < cut)[0]
above = [i for i in pre if v[i] >= 0.2]
last_above = above[-1] if above else None
first_below = (last_above + 1) if last_above is not None else pre[0]
start = ts[first_below]
dt = np.diff(ts[pre]); gap_max = float(dt.max()) if len(dt) else None
after = np.where((ts >= cut) & (ts <= cut + 30.0))[0]
res = {"ulg": sys.argv[1], "groundtruth_rate_hz": round(1 / float(np.median(np.diff(ts))), 1), "pub_minus_sample_ms_median": round(float(np.median(tpub - ts)) * 1e3, 2),
       "finished_t": fin[0] if fin else None, "cut_candidates": cut_candidates, "cut_used": cut,
       "last_ge_0.2_t": None if last_above is None else float(ts[last_above]), "first_lt_0.2_after_t": float(start),
       "slow_until_cut_lower_bound_s": round(cut - float(start), 3), "pass_1s": bool(cut - float(start) >= 1.0),
       "disp_start_to_cut_m": round(float(np.hypot(g["x"][(ts >= start) & (ts <= cut)] - g["x"][first_below], g["y"][(ts >= start) & (ts <= cut)] - g["y"][first_below]).max()), 4),
       "disp_cut_to_30s_m": round(float(np.hypot(g["x"][after] - g["x"][after[0]], g["y"][after] - g["y"][after[0]]).max()), 4) if len(after) else None, "gt_gap_max_before_cut_s": None if gap_max is None else round(gap_max, 4),
       "v_max_between_start_and_cut": round(float(v[(ts >= start) & (ts < cut)].max()), 4),
       "v_max_30s_after_cut": round(float(v[after].max()), 4) if len(after) else None,
       "speed_samples_around": [(round(float(t), 3), round(float(x), 3)) for t, x in zip(ts, v) if start - 1.0 <= t <= cut + 0.5][::5],
       "notes": ["groundtruth 는 PX4 gz 브리지가 Gazebo odometry 를 받아 publish — timestamp_sample 은 브리지 수신 기준 (물리 생성 시각과 같은 sim 시계, 지연은 pub−sample 로만 표시)",
                 "저속 시작 = 마지막 ≥ 0.2 뒤 첫 < 0.2 표본 (보수적: 실제 교차는 더 이를 수 있음)", "차단 경계 = min(disarm 요청, armed 해제); actuator_outputs 변화는 기록"]}
json.dump(res, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "speed_samples_around"}, ensure_ascii=False, indent=1))
