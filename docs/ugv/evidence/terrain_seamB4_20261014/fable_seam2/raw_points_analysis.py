"""Fable 검토 2 (읽기 전용) — seamB4 점별 원본 (gz_detail_seam_v3 --raw JSONL) 독립 재계산.
질문 1 (Codex 102008): 엔진 body 순서를 힘 부호가 아닌 **법선 방향 (DART: normal = body2→body1)** 과 기하 (바퀴는 지형 위) 로 정규화하고,
점별 힘을 바퀴에 작용하는 힘 F_w 로 통일한 뒤 (a) 점별 fn·ft·비, (b) 두 마찰 기저 후보 (DART 기본 UnitZ / fdir1=차량 전방) 로 λ1·λ2 분해해
상자 한계 |λ|≤μ·λn 를 전 점에서 만족하는 기저를 찾는다, (c) 바퀴별 순힘·앞축 축방향 합, (d) 시간 변화 (점 수·위치·깊이·힘).
사용: python raw_points_analysis.py <runs_dir> <out_json> <out_tsv>
"""
import json, math, sys
import numpy as np
from pathlib import Path

RUNS = Path(sys.argv[1]); OUT = Path(sys.argv[2]); TSV = Path(sys.argv[3])
W = ["wheel_front_left", "wheel_front_right", "wheel_rear_left", "wheel_rear_right"]
MU = 1.0
EDGE_Y = -4631.0
FDIR_WORLD = np.array([0.0, 1.0, 0.0])      # 차량 yaw π/2 → 바퀴 collision x (fdir1) = 월드 +y
UNITZ = np.array([0.0, 0.0, 1.0])

def unit(v):
    v = np.asarray(v, float); n = np.linalg.norm(v); return v / n if n > 0 else v
def rot_about(axis, ang, v):
    axis = unit(axis); return v * math.cos(ang) + np.cross(axis, v) * math.sin(ang) + axis * np.dot(axis, v) * (1 - math.cos(ang))
def basis(n, first):
    """DART getTangentBasisMatrixODE: tangent = n × first (정규화); col0 = tangent 를 n 둘레로 +90° 회전; col1 = tangent."""
    t = np.cross(n, first)
    if np.linalg.norm(t) < 1e-6:
        t = np.cross(n, np.array([1.0, 0, 0]))
    t = unit(t); c0 = rot_about(n, math.pi / 2, t); return c0, t

def analyze(tag):
    rows = [json.loads(l) for l in open(RUNS / f"{tag}_raw.jsonl", encoding="utf-8")]
    t0 = rows[0]["sim_t"]
    res = {"tag": tag, "samples": len(rows), "t0": t0, "n_z_negative_points": 0, "f_dot_n_negative_points": 0, "points_total": 0}
    per = {w: {"fn": [], "ft": [], "ratio": [], "lam_unitz": [], "lam_fdir": [], "npts": [], "depth": [], "pos_x": [], "pos_y": [], "tilt": [],
               "Fw_sum": [], "dy_edge": [], "t": []} for w in W}
    series = []
    for r in rows:
        t = r["sim_t"]
        if t - t0 < 2.0:                     # 정착 2 s 제외 (기존 분석과 같음)
            continue
        line = {"t": round(t, 3)}
        for w in W:
            m = r["wheels"].get(w)
            if not m or not m.get("pts"):
                per[w]["npts"].append(0); line[w] = None; continue
            Fw = np.zeros(3); fns = []; pts_out = []
            for p in m["pts"]:
                if "n" not in p or "f1" not in p:
                    continue
                res["points_total"] += 1
                n = np.asarray(p["n"], float); f1 = np.asarray(p["f1"], float)
                # 엔진 body1 = 법선이 가리키는 쪽. 지형 위 바퀴이므로 n_z>0 ⇔ body1 = 바퀴 (힘 부호 사용 안 함)
                if n[2] < 0:
                    res["n_z_negative_points"] += 1; n_up = -n; Fw_p = -f1       # body1 = 지형 → 바퀴 힘 = f2 = −f1
                else:
                    n_up = n; Fw_p = f1
                fn = float(np.dot(Fw_p, n_up)); ftv = Fw_p - fn * n_up; ft = float(np.linalg.norm(ftv))
                if fn < 0:
                    res["f_dot_n_negative_points"] += 1
                c0, c1 = basis(n_up, UNITZ); l1z, l2z = float(np.dot(Fw_p, c0)), float(np.dot(Fw_p, c1))
                d0, d1 = basis(n_up, FDIR_WORLD); l1f, l2f = float(np.dot(Fw_p, d0)), float(np.dot(Fw_p, d1))
                per[w]["fn"].append(fn); per[w]["ft"].append(ft); per[w]["ratio"].append(ft / fn if fn > 1 else float("nan"))
                per[w]["lam_unitz"].append((abs(l1z) / fn if fn > 1 else float("nan"), abs(l2z) / fn if fn > 1 else float("nan")))
                per[w]["lam_fdir"].append((abs(l1f) / fn if fn > 1 else float("nan"), abs(l2f) / fn if fn > 1 else float("nan")))
                per[w]["depth"].append(p.get("d", float("nan"))); per[w]["pos_x"].append(p["pos"][0]); per[w]["pos_y"].append(p["pos"][1])
                per[w]["dy_edge"].append(p["pos"][1] - EDGE_Y); per[w]["tilt"].append(math.degrees(math.acos(min(1, n_up[2]))))
                Fw += Fw_p; fns.append(fn)
                pts_out.append({"x": round(p["pos"][0], 4), "dy_edge_mm": round((p["pos"][1] - EDGE_Y) * 1000, 3), "d_mm": round(p.get("d", float("nan")) * 1000, 3),
                                "fn": round(fn, 1), "fx": round(Fw_p[0], 1), "fy": round(Fw_p[1], 1), "ratio": round(ft / fn, 3) if fn > 1 else None,
                                "lamZ": (round(l1z / fn, 3), round(l2z / fn, 3)) if fn > 1 else None})
            per[w]["npts"].append(len(pts_out)); per[w]["Fw_sum"].append(Fw.tolist()); per[w]["t"].append(t)
            line[w] = {"n": len(pts_out), "Fx": round(Fw[0], 1), "Fy": round(Fw[1], 1), "Fz": round(Fw[2], 1), "pts": pts_out}
        series.append(line)
    def q(a):
        a = [x for x in a if x == x]; return None if not a else {"min": round(min(a), 4), "med": round(float(np.median(a)), 4), "max": round(max(a), 4), "n": len(a)}
    res["wheels"] = {}
    for w in W:
        P = per[w]
        lz = [max(a, b) for a, b in P["lam_unitz"] if a == a]; lf = [max(a, b) for a, b in P["lam_fdir"] if a == a]
        res["wheels"][w] = {"npts_hist": {str(k): P["npts"].count(k) for k in sorted(set(P["npts"]))}, "fn": q(P["fn"]), "ft": q(P["ft"]), "ratio_ft_fn": q(P["ratio"]),
                            "max_abs_lambda_over_fn_basis_UnitZ": q(lz), "max_abs_lambda_over_fn_basis_fdir": q(lf),
                            "n_points_violating_box_UnitZ": sum(1 for v in lz if v > MU + 0.02), "n_points_violating_box_fdir": sum(1 for v in lf if v > MU + 0.02),
                            "depth_mm": q([d * 1000 for d in P["depth"]]), "pos_x_values": sorted({round(x, 3) for x in P["pos_x"]}),
                            "dy_edge_mm": q([d * 1000 for d in P["dy_edge"]]), "tilt_deg": q(P["tilt"]),
                            "Fw_sum_mean": [round(float(v), 1) for v in np.mean(np.array(P["Fw_sum"]), axis=0)] if P["Fw_sum"] else None,
                            "Fw_sum_x_minmax": [round(float(min(v[0] for v in P["Fw_sum"])), 1), round(float(max(v[0] for v in P["Fw_sum"])), 1)] if P["Fw_sum"] else None}
    # 앞축 축방향 합 (월드 x), 네 바퀴 합
    FL = np.array(per[W[0]]["Fw_sum"]); FR = np.array(per[W[1]]["Fw_sum"]); RL = np.array(per[W[2]]["Fw_sum"]); RR = np.array(per[W[3]]["Fw_sum"])
    nmin = min(len(FL), len(FR), len(RL), len(RR))
    tot = FL[:nmin] + FR[:nmin] + RL[:nmin] + RR[:nmin]
    res["front_axle_x_sum_FL_plus_FR"] = q(list((FL[:nmin] + FR[:nmin])[:, 0]))
    res["all_wheels_sum"] = {"Fx": q(list(tot[:, 0])), "Fy": q(list(tot[:, 1])), "Fz": q(list(tot[:, 2]))}
    # 시간 변화: FR 점 수 변화 횟수, FR 깊이 변화, FL/FR Fx 변화
    npFR = per[W[1]]["npts"]; res["FR_npts_changes"] = sum(1 for a, b in zip(npFR, npFR[1:]) if a != b)
    res["series_head"] = series[:3]; res["series_tail"] = series[-2:]
    # 표 (시계열)
    with open(TSV, "a", encoding="utf-8") as f:
        f.write(f"# {tag}\nt\tFL_n\tFL_Fx\tFL_Fz\tFL_d_mm\tFL_dy_mm\tFR_n\tFR_Fx\tFR_Fz\tFR_d_mm(pts)\tFR_dy_mm(pts)\tFR_x(pts)\tRL_Fx\tRR_Fx\n")
        for l in series:
            def g(w, k, dflt=""):
                return l[w][k] if l.get(w) else dflt
            fl, fr = l.get(W[0]), l.get(W[1])
            f.write(f"{l['t']}\t{g(W[0],'n')}\t{g(W[0],'Fx')}\t{g(W[0],'Fz')}\t{fl['pts'][0]['d_mm'] if fl and fl['pts'] else ''}\t{fl['pts'][0]['dy_edge_mm'] if fl and fl['pts'] else ''}\t"
                    f"{g(W[1],'n')}\t{g(W[1],'Fx')}\t{g(W[1],'Fz')}\t{[p['d_mm'] for p in fr['pts']] if fr else ''}\t{[p['dy_edge_mm'] for p in fr['pts']] if fr else ''}\t{[p['x'] for p in fr['pts']] if fr else ''}\t{g(W[2],'Fx')}\t{g(W[3],'Fx')}\n")
    return res

out = {}
open(TSV, "w", encoding="utf-8").close()
for tag in ("b4e_exact", "b4d_N", "b4d_S"):
    if (RUNS / f"{tag}_raw.jsonl").exists():
        out[tag] = analyze(tag)
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for tag, r in out.items():
    print("=====", tag, "samples", r["samples"], "pts", r["points_total"], "n_z<0:", r["n_z_negative_points"], "f·n<0:", r["f_dot_n_negative_points"], "FR npts changes:", r["FR_npts_changes"])
    print(" front axle Fx FL+FR:", r["front_axle_x_sum_FL_plus_FR"], " all Fz:", r["all_wheels_sum"]["Fz"], " all Fx:", r["all_wheels_sum"]["Fx"])
    for w, d in r["wheels"].items():
        print(" ", w[6:], json.dumps({k: d[k] for k in ("npts_hist", "fn", "ratio_ft_fn", "max_abs_lambda_over_fn_basis_UnitZ", "max_abs_lambda_over_fn_basis_fdir", "n_points_violating_box_UnitZ", "n_points_violating_box_fdir", "depth_mm", "pos_x_values", "dy_edge_mm", "tilt_deg", "Fw_sum_mean", "Fw_sum_x_minmax")}, ensure_ascii=False))
    print("  head:", json.dumps(r["series_head"][0], ensure_ascii=False)[:900])
