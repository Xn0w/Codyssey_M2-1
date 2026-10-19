# -*- coding: utf-8 -*-
"""교차로 494862 단독 재현 판정 v2 (시험 도구 — 제품 코드 아님). 원본 judge_corner.py 는 그대로 보존한다.

사용: python judge_corner_v2.py <실행 폴더> <계획 json> [--lat 1.0] [--out <출력 json>] [--arcs-json <생성 원호 json>]
  출력은 실행 폴더에 쓰지 않는다 (기본: corner494862/v2/judge/<실행 이름>__<계획 이름>.json).

v2 가 고친 계측 결함 (2026-10-19 검증보완계획 §3):
  (a) 원본은 계획선을 0.25 m 로 직선 보간한 점에서 앞뒤 '인덱스' 10 개(=2.5 m 가정) 세 점 원으로 반경을 쟀다. 보간 선분의 실제 길이가
      원래 선분마다 달라 창 길이가 달라지고, 현(弦) 위 보간점이 원 안쪽에 있어 반경을 작게 봤다 (회전 3: 기하 10.28 m → 9.22 m).
      v2: 계획선의 '원래 점'에서 같은 원 위의 연속 점 묶음을 찾아 최소제곱(기하 거리) 원 맞춤. 잔차·점 수·각도 범위·방향을 기록.
  (b) 정점 = 최소 반경 표본 (표본화에 좌우) → v2: 원호 진행거리 중앙 (= 일정 반경 원호의 회전각 중앙).
  (c) 투영 탐색 시작 인덱스를 int(s/0.25) 로 잡던 것 → 실제 누적거리에서 bisect.
  (d) ARC_R_MAX=15 라 25~40 m 원호가 빠짐 → v2 는 R ≤ ARC_REPORT_R_MAX 원호를 모두 보고. 원본 회전 번호는 s 구간 겹침으로 대응.
  허용치 규칙·속도 계측(±0.25 s 차분)·진입 창(2 m)·정점 창(±2 m)·투영 거리 조건은 원본과 같다 (결과가 좋아진다고 키우지 않는다).
  영향 분리: 각 회전에 대해 old(원본 창+원본 반경), r_only(원본 창+v2 반경), win_only(v2 창+원본 반경), v2 를 함께 낸다.
  --arcs-json: 제품이 만든 생성 원호 정보 [{"s0","s1","R"}...] 를 주면 좌표 맞춤과 대조해 불일치를 기록 (정답으로 쓰지 않음).
"""
import argparse
import bisect
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
# ---- 원본과 같은 값
ARC_R_MAX_OLD = 15.0
CURV_W_OLD = 2.5
ENTRY_LOOK_M = 2.0
APEX_HALF_M = 2.0
ACCEPT_M = 3.0             # PX4 NAV_ACC_RAD (ugv/drivers/px4.py ACCEPT_M) — 위치별 항목 속도 추정용
# ---- v2 원호 검출 (실행 전 고정, 근거)
RES_TOL_M = 0.015          # 원 맞춤 최대 잔차: plan_xy 좌표 0.01 m 반올림(점당 ≤ 0.0071 m) × 2 여유. 생성 원호 점은 정확히 원 위
ARC_MIN_PTS = 4            # 원래 점 최소 4 개 (세 점은 항상 원 하나 — 확인 불가)
ARC_MIN_DEG = 5.0          # 이보다 작은 회전각은 미확인 (거의 일직선)
ARC_MAX_CHORD_M = 2.6      # 생성 원호 표본 간격 상한 2.0 m (drive_graph.ARC_STEP_M) + 반올림 여유 — 이보다 긴 현은 원호 표본 아님
ARC_DET_R_MAX = 300.0      # 검출 상한 (그 위는 직선 취급)
ARC_REPORT_R_MAX = 60.0    # 판정 표에 올리는 반경 상한 (25~40 m 범위 포함)
UNIFORM_CV = 0.02          # 내부 현 길이 변동계수가 이 이하이면 '균등 표본 원호' — 양 끝 현이 5 % 넘게 다르면 그 끝 점을 뺀다


def radius3(a, b, c):
    area2 = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
    den = math.dist(a, b) * math.dist(b, c) * math.dist(a, c)
    return math.inf if area2 < 1e-9 else den / (2 * area2)


def densify(pts, step=0.25):
    out = [pts[0]]
    for p, q in zip(pts, pts[1:]):
        n = max(1, math.ceil(math.dist(p, q) / step))
        out += [(p[0] + (q[0] - p[0]) * k / n, p[1] + (q[1] - p[1]) * k / n) for k in range(1, n + 1)]
    return out


def cumlen(pts):
    c = [0.0]
    for p, q in zip(pts, pts[1:]):
        c.append(c[-1] + math.dist(p, q))
    return c


def fit_circle(P):
    """기하 거리 최소제곱 원 (Kasa 초기값 → Gauss-Newton). 반환 (cx, cy, R, 최대 잔차, 부호 있는 회전각 rad)."""
    Q = np.asarray(P, dtype=float)
    o = Q.mean(0)
    X = Q - o                                            # 중심 이동 (큰 좌표 수치 오차 방지)
    A = np.c_[2 * X[:, 0], 2 * X[:, 1], np.ones(len(X))]
    b = (X ** 2).sum(1)
    try:
        cx, cy, c = np.linalg.lstsq(A, b, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    R = math.sqrt(max(c + cx * cx + cy * cy, 0.0))
    for _ in range(20):
        d = np.hypot(X[:, 0] - cx, X[:, 1] - cy)
        if np.any(d < 1e-9):
            return None
        J = np.c_[-(X[:, 0] - cx) / d, -(X[:, 1] - cy) / d, -np.ones(len(X))]
        r = d - R
        try:
            step = np.linalg.lstsq(J, -r, rcond=None)[0]
        except np.linalg.LinAlgError:
            break
        cx, cy, R = cx + step[0], cy + step[1], R + step[2]
        if np.abs(step).max() < 1e-10:
            break
    d = np.hypot(X[:, 0] - cx, X[:, 1] - cy)
    res = float(np.abs(d - R).max())
    ang = np.unwrap(np.arctan2(X[:, 1] - cy, X[:, 0] - cx))
    return (cx + o[0], cy + o[1], float(R), res, float(ang[-1] - ang[0]))


def detect_arcs(P, cum):
    """원래 점 P 에서 같은 원 위 연속 점 묶음 → [{i0, i1, s0, s1, R, res, n, deg, dir, uniform, status}].
    직선·짧은 구간·중복점·거의 일직선은 status 'UNCONFIRMED' 로 남기거나 버린다 (판정에 쓰지 않음)."""
    n = len(P)
    out, i = [], 0
    while i < n - 3:
        if any(math.dist(P[k], P[k + 1]) < 1e-6 or math.dist(P[k], P[k + 1]) > ARC_MAX_CHORD_M for k in (i, i + 1, i + 2)):
            i += 1
            continue
        f = fit_circle(P[i:i + 4])
        if f is None or f[2] > ARC_DET_R_MAX or f[3] > RES_TOL_M:
            i += 1
            continue
        j = i + 3
        while j + 1 < n and 1e-6 < math.dist(P[j], P[j + 1]) <= ARC_MAX_CHORD_M:
            g = fit_circle(P[i:j + 2])
            if g is None or g[3] > RES_TOL_M or g[2] > ARC_DET_R_MAX:
                break
            f, j = g, j + 1
        a, b = i, j
        ch = [math.dist(P[k], P[k + 1]) for k in range(a, b)]
        uniform = False
        if len(ch) >= 4:
            inner = ch[1:-1]
            m = sum(inner) / len(inner)
            cv = (sum((x - m) ** 2 for x in inner) / len(inner)) ** 0.5 / m
            if cv <= UNIFORM_CV:
                uniform = True
                if abs(ch[0] / m - 1) > 0.05 and b - a - 1 >= ARC_MIN_PTS - 1:
                    a += 1
                if abs(ch[-1] / m - 1) > 0.05 and b - 1 - a >= ARC_MIN_PTS - 1:
                    b -= 1
                if (a, b) != (i, j):
                    f = fit_circle(P[a:b + 1])
        cx, cy, R, res, sweep = f
        deg = abs(math.degrees(sweep))
        status = "CONFIRMED" if (b - a + 1 >= ARC_MIN_PTS and deg >= ARC_MIN_DEG) else "UNCONFIRMED"
        out.append({"i0": a, "i1": b, "s0": cum[a], "s1": cum[b], "R": R, "res_max_m": res, "n_pts": b - a + 1,
                    "deg": deg, "dir": "L" if sweep > 0 else "R", "uniform": uniform, "center": (cx, cy), "status": status})
        i = max(b, i + 1)
    return out


def project_seg(P, cum, x, y, k0, k1):
    best = (math.inf, 0.0)
    for k in range(max(k0, 0), min(k1, len(P) - 1)):
        a, b = P[k], P[k + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / L2))
        d = math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)
        if d < best[0]:
            best = (d, cum[k] + t * (cum[k + 1] - cum[k]))
    return best


def track_speeds(rows, half_s=0.25):
    T = [r["sim_t"] for r in rows]
    v = []
    for i in range(len(rows)):
        j = i
        while j > 0 and T[i] - T[j] < half_s:
            j -= 1
        k = i
        while k < len(rows) - 1 and T[k] - T[i] < half_s:
            k += 1
        dt = T[k] - T[j]
        v.append(math.dist((rows[k]["x"], rows[k]["y"]), (rows[j]["x"], rows[j]["y"])) / dt if dt > 0 else 0.0)
    return v


def old_arcs(pxy):
    """원본 judge_corner.py 와 같은 계산 (재현 확인·영향 분리용)."""
    dense = densify(pxy)
    dc = cumlen(dense)
    w = int(CURV_W_OLD / 0.25)
    R = [math.inf] * len(dense)
    for i in range(w, len(dense) - w):
        R[i] = radius3(dense[i - w], dense[i], dense[i + w])
    arcs, cur = [], None
    for i, r in enumerate(R):
        if r < ARC_R_MAX_OLD and cur is None:
            cur = [i, i]
        elif r < ARC_R_MAX_OLD:
            cur[1] = i
        elif cur is not None:
            arcs.append(cur)
            cur = None
    if cur:
        arcs.append(cur)
    arcs = [c for c in arcs if dc[c[1]] - dc[c[0]] >= 3.0]
    res = []
    for i0, i1 in arcs:
        ia = min(range(i0, i1 + 1), key=lambda i: R[i])
        res.append({"s0": dc[i0], "s1": dc[i1], "R": min(R[i0:i1 + 1]), "s_apex": dc[ia]})
    return res, dense, dc


def load_track(run):
    from ugv.geo import FRAME, GZ_FRAME
    csvs = sorted(run.glob("corner_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    rows = []
    with open(csvs[0], newline="") as f:
        for r in csv.DictReader(f):
            try:
                t, gx, gy = float(r["sim_t"]), float(r["x"]), float(r["y"])
            except ValueError:
                continue
            lat, lon = GZ_FRAME.to_ll(gx, gy)
            x, y = FRAME.to_xy(lat, lon)
            rows.append({"sim_t": t, "x": x, "y": y})
    return rows, csvs[0].name


def evaluate(rows, plan, lat_accel, carried=None, gen_arcs=None, tol_exclude="old"):
    """rows: [{sim_t, x, y}] 계획 좌표계. plan: {"plan_xy","plan_v","items":[(x,y,v)]}. 판정 dict 를 돌려준다."""
    pxy = [tuple(p) for p in plan["plan_xy"]]
    pv = plan["plan_v"]
    items = plan["items"]
    pc = cumlen(pxy)
    vs = track_speeds(rows)
    # 진행 거리 (단조 탐색: 지난 위치 10 m 뒤 ~ 100 m 앞 선분 — 원본의 dense 인덱스 −40/+400 과 같은 거리. 시작 인덱스는 누적거리에서 bisect)
    S, D = [], []
    s_lo = 0.0
    for r in rows:
        k0 = max(0, bisect.bisect_left(pc, s_lo - 10.0) - 1)
        k1 = bisect.bisect_right(pc, s_lo + 100.0) + 1
        d, s = project_seg(pxy, pc, r["x"], r["y"], k0, k1)
        S.append(s)
        D.append(d)
        s_lo = max(s_lo, s)
    item_s = [project_seg(pxy, pc, x, y, 0, len(pxy))[1] for x, y, _ in items]
    T = [r["sim_t"] for r in rows]
    acc = [0.0] * len(rows)
    for i in range(len(rows)):
        j, k = max(0, i - 10), min(len(rows) - 1, i + 10)
        acc[i] = (vs[k] - vs[j]) / (T[k] - T[j]) if T[k] > T[j] else 0.0
    mv = next((i for i, x in enumerate(vs) if x >= 0.3), len(vs))
    still = vs[:max(0, mv - 10)]
    sig = (math.sqrt(sum((x - sum(still) / len(still)) ** 2 for x in still) / len(still)) if len(still) >= 10 else None)
    oarcs, _, _ = old_arcs(pxy)
    arcs = detect_arcs(pxy, pc)
    conf = [a for a in arcs if a["status"] == "CONFIRMED" and a["R"] <= ARC_REPORT_R_MAX]
    # 허용치: 원본과 같은 규칙·같은 제외 구간(원본 원호 ±3 m) — 허용치는 원본 값을 보존한다
    # tol_exclude "old": 원본 원호(R<15)만 제외 (r20·fixv 재분석 — 원본 허용치 보존). "v2": v2 확인 원호(R ≤ 60) 모두 제외 — 원본 규칙의
    # '원호 밖' 의도를 25~40 m 원호 사례에 적용 (대표 반경 사례용, 실행 전 고정 2026-10-19)
    ex_arcs = oarcs if tol_exclude == "old" else [{"s0": a["s0"], "s1": a["s1"]} for a in conf]
    in_old = lambda s: any(c["s0"] - 3 <= s <= c["s1"] + 3 for c in ex_arcs)
    exc = []
    for i in range(len(rows)):
        if S[i] < 15.0 or D[i] >= 3.0 or abs(acc[i]) >= 0.3 or in_old(S[i]):
            continue
        k = next((n for n, si in enumerate(item_s) if si >= S[i]), None)
        if k is not None:
            exc.append(vs[i] - items[k][2])
    exc.sort()
    e95 = exc[int(0.95 * (len(exc) - 1))] if len(exc) >= 20 else None
    tol = max(0.15, (e95 or 0.0) + 2 * (sig or 0.0))

    def plan_at(s):
        k = min(max(1, bisect.bisect_left(pc, s)), len(pc) - 1)
        return pv[k - 1] + (pv[k] - pv[k - 1]) * ((s - pc[k - 1]) / (pc[k] - pc[k - 1]) if pc[k] > pc[k - 1] else 0.0)

    def item_at(s):
        """위치 s 에서 PX4 가 쓰는 구간 속도 추정: 도착 반경(ACCEPT_M) 안에 든 지점은 지나간 것으로 본다"""
        k = next((n for n, si in enumerate(item_s) if si > s + ACCEPT_M), len(items) - 1)
        return items[k][2]

    def windows(s0, s1, s_apex, R):
        vc = math.sqrt(lat_accel * R)
        ent = [vs[i] for i in range(len(rows)) if s0 - ENTRY_LOOK_M <= S[i] <= s0 and D[i] < 5.0]
        apex = [vs[i] for i in range(len(rows)) if abs(S[i] - s_apex) <= APEX_HALF_M and D[i] < 5.0]
        over = [vs[i] - plan_at(S[i]) for i in range(len(rows)) if s0 <= S[i] <= s1 and D[i] < 5.0]
        over_vc = [vs[i] - vc for i in range(len(rows)) if s0 <= S[i] <= s1 and D[i] < 5.0]
        return {"R_m": round(R, 3), "v_curve_mps": round(vc, 3), "s_m": [round(s0, 2), round(s1, 2)], "s_apex_m": round(s_apex, 2),
                "v_entry_max_mps": round(max(ent), 3) if ent else None, "v_apex_max_mps": round(max(apex), 3) if apex else None,
                "arc_max_over_plan_mps": round(max(over), 3) if over else None,
                "arc_max_over_vcurve_mps": round(max(over_vc), 3) if over_vc else None,
                "entry_ok": None if not ent else max(ent) <= vc + tol, "apex_ok": None if not apex else max(apex) <= vc + tol,
                "arc_vs_plan_ok": None if not over else max(over) <= tol,
                "arc_vs_vcurve_ok": None if not over_vc else max(over_vc) <= tol,
                "n_entry": len(ent), "n_apex": len(apex), "n_arc": len(over)}

    reach_s = max(S) if S else 0.0
    corners = []
    used = set()
    # 원본 회전(R<15) ↔ v2 원호 대응: s 구간 겹침이 가장 큰 확인 원호
    for n, oc in enumerate(oarcs):
        best, bo = None, 0.0
        for m, a in enumerate(conf):
            ov = min(oc["s1"], a["s1"]) - max(oc["s0"], a["s0"])
            if ov > bo:
                best, bo = m, ov
        rec = {"corner": n + 1, "old": windows(oc["s0"], oc["s1"], oc["s_apex"], oc["R"])}
        if best is not None:
            used.add(best)
            a = conf[best]
            sm = (a["s0"] + a["s1"]) / 2
            rec["arc"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in a.items() if k != "center"}
            rec["r_only"] = windows(oc["s0"], oc["s1"], oc["s_apex"], a["R"])
            rec["win_only"] = windows(a["s0"], a["s1"], sm, oc["R"])
            rec["v2"] = windows(a["s0"], a["s1"], sm, a["R"])
        corners.append(rec)
    extra = []
    for m, a in enumerate(conf):
        if m in used:
            continue
        sm = (a["s0"] + a["s1"]) / 2
        extra.append({"arc": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in a.items() if k != "center"},
                      "v2": windows(a["s0"], a["s1"], sm, a["R"])})
    # 원호 위·전후 위치별 기록 (진입 전 5 m / 원호 / 출구 후 5 m): 실제 속도·같은 위치 계획 속도·PX4 구간 속도 추정
    def profile(a):
        out = []
        for i in range(len(rows)):
            if a["s0"] - 5 <= S[i] <= a["s1"] + 5 and D[i] < 5.0:
                zone = "pre" if S[i] < a["s0"] else ("arc" if S[i] <= a["s1"] else "post")
                out.append([round(S[i], 2), zone, round(vs[i], 3), round(plan_at(S[i]), 3), item_at(S[i])])
        return out
    for c in corners:
        if "arc" in c:
            c["profile_s_zone_v_plan_item"] = profile(conf[[m for m in range(len(conf)) if conf[m]["i0"] == c["arc"]["i0"]][0]])
    gen_cmp = None
    if gen_arcs:
        gen_cmp = []
        for g in gen_arcs:
            best = min(conf + [a for a in arcs if a not in conf], key=lambda a: abs(a["s0"] - g["s0"]) + abs(a["s1"] - g["s1"]),
                       default=None)
            gen_cmp.append({"gen": g, "fit": None if best is None else {"s0": round(best["s0"], 3), "s1": round(best["s1"], 3),
                                                                        "R": round(best["R"], 4), "res": best["res_max_m"]},
                            "dR_m": None if best is None else round(best["R"] - g["R"], 4)})
    return {"tolerance": {"value_mps": round(tol, 3), "rule": "max(0.15, e95 + 2*sigma_meas) (원본과 같음)", "exclude_arcs": tol_exclude,
                          "e95_steady_excess_mps": None if e95 is None else round(e95, 3),
                          "sigma_meas_mps": None if sig is None else round(sig, 3), "n_samples": len(exc)},
            "reach_s_m": round(reach_s, 2), "plan_len_m": round(pc[-1], 2),
            "arcs_detected": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in a.items() if k != "center"} for a in arcs],
            "corners": corners, "extra_arcs": extra, "gen_arc_compare": gen_cmp,
            "item_speeds_near_arcs": [[round(si, 2), it[2]] for si, it in zip(item_s, items)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--lat", type=float, default=1.0)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--arcs-json", type=Path, default=None)
    ap.add_argument("--tol-exclude", choices=("old", "v2"), default="old")
    a = ap.parse_args()
    sys.path.insert(0, str(HERE.parents[3]))
    from ugv.geo import FRAME, GZ_FRAME
    plan = json.loads(a.plan.read_text(encoding="utf-8"))
    pl = {"plan_xy": plan["plan_xy"], "plan_v": plan["plan_v"],
          "items": [(*FRAME.to_xy(i["lat"], i["lon"]), i["speed_mps"]) for i in plan["items"]]}
    rows, csvname = load_track(a.run)
    carried = []
    us = a.run / "ulog_speed.csv"
    if us.exists():
        with open(us, newline="") as f:
            for r in csv.DictReader(f):
                if r["kind"] == "triplet" and r["lat"] not in ("nan", "") and float(r["cruising_speed"]) > 0:
                    x, y = GZ_FRAME.to_xy(float(r["lat"]), float(r["lon"]))
                    lat, lon = GZ_FRAME.to_ll(x, y)
                    carried.append({"xy": FRAME.to_xy(lat, lon), "v": float(r["cruising_speed"])})
    gen = json.loads(a.arcs_json.read_text(encoding="utf-8")) if a.arcs_json else plan.get("plan_arcs")
    out = {"judge": "judge_corner_v2", "run": a.run.name, "plan": a.plan.name, "track_csv": csvname, "lat_accel": a.lat,
           "eta_sec": plan.get("eta_sec")}
    out.update(evaluate(rows, pl, a.lat, carried, gen, a.tol_exclude))
    # PX4 실린 속도 (ulog triplet) — 원호 s 구간 ±3 m 안 (원본과 같은 방식, 위치 기준)
    pxy = [tuple(p) for p in plan["plan_xy"]]
    pc = cumlen(pxy)
    cs = [(project_seg(pxy, pc, *c["xy"], 0, len(pxy))[1], c["v"]) for c in carried]
    for c in out["corners"] + out["extra_arcs"]:
        w = c.get("v2") or c.get("old")
        s0, s1 = w["s_m"]
        c["px4_carried_arc"] = [v for s, v in cs if s0 - 3 <= s <= s1 + 3]
    try:
        fin = json.loads((a.run / "ugv_final.json").read_text(encoding="utf-8"))
        out["final"] = {k: fin[0].get(k) for k in ("state", "fault")} if isinstance(fin, list) and fin else None
    except Exception:  # noqa: BLE001
        out["final"] = None
    try:
        t = list(json.loads((a.run / "state" / "ugv_tasks.json").read_text(encoding="utf-8"))["tasks"].values())[-1]
        out["task"] = {k: t.get(k) for k in ("status", "mission_result", "physical_state", "error")}
    except Exception:  # noqa: BLE001
        out["task"] = None
    dst = a.out or (HERE / "v2" / "judge" / f"{a.run.name}__{a.plan.stem}.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"run": out["run"], "out": str(dst), "tol": out["tolerance"]["value_mps"],
                      "corners": [[c["corner"], c.get("v2", {}).get("R_m"), c.get("v2", {}).get("entry_ok"),
                                   c.get("v2", {}).get("apex_ok"), c.get("v2", {}).get("arc_vs_plan_ok")] for c in out["corners"]]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
