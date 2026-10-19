# -*- coding: utf-8 -*-
"""교차로 494862 단독 재현 판정 (시험 도구 — 제품 코드 아님).

사용: python judge_corner.py <실행 폴더> <계획 json (plan_offline.sh)> [--lat 1.0]

통과 기준 (2026-10-17 사용자 확정 조건):
  ① 494862 원호 진입 전 실제 속도(Gazebo 궤적) ≤ 회전반경 기준 곡선 속도 √(횡가속 × R) + 허용치
  ② 원호 정점(최소 반경 ±2 m) 실제 속도 ≤ 같은 곡선 속도 + 허용치, 원호 안 실제 속도 ≤ 같은 위치 계획 속도 + 허용치 (출구 가속은 계획대로 허용)
     (참고: v_arc_max_mps 는 출구 가속 포함 최고 속도 — 판정에 쓰지 않음)
  ③ 임무 결과 (도착·고장 코드) 와 PX4 에 실린 구간 속도(ulog triplet cruising_speed) 기록
위치 기준으로 맞춘다 (궤적 점을 계획 선형에 투영한 진행 거리 s) — ulog·궤적 시계 정렬이 필요 없다.

허용치 (근거를 결과에 함께 남긴다):
  - 궤적 속도 계측 잡음 σ_meas: Gazebo 자세(약 20 Hz) ±0.25 s 차분, 출발 전 정차 구간 표준편차
  - PX4 정속 추종 오차 e95: 정속 표본(|가속|<0.3 m/s², 원호 밖)에서 (실제 − 실린 항목 속도) 95 백분위
  - 허용치 = max(0.15, e95 + 2 σ_meas) m/s
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

ARC_R_MAX = 15.0          # 이 반경보다 급한 계획 선형 구간을 교차로 원호로 본다
CURV_W = 2.5              # 반경 계산 앞뒤 거리 (원호 판별용)
ENTRY_LOOK_M = 2.0        # 원호 시작점 앞 이 거리 안 실제 속도의 최대를 '진입 속도'로


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


def project(pts, cum, x, y, lo=0, hi=None):
    best = (math.inf, 0.0)
    hi = len(pts) - 1 if hi is None else hi
    for k in range(max(lo, 0), min(hi, len(pts) - 1)):
        a, b = pts[k], pts[k + 1]
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--lat", type=float, default=1.0)
    a = ap.parse_args()
    plan = json.loads(a.plan.read_text(encoding="utf-8"))
    from_frame = None
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    from ugv.geo import FRAME, GZ_FRAME           # 계획 xy = FRAME, 궤적 xy = Gazebo ENU — 위경도로 맞춘다
    pxy = [tuple(p) for p in plan["plan_xy"]]
    pv = plan["plan_v"]
    items = [(FRAME.to_xy(i["lat"], i["lon"]), i["speed_mps"]) for i in plan["items"]]
    dense = densify(pxy)
    dc = cumlen(dense)
    pc = cumlen(pxy)
    # 원호 구간: 0.25 m 표본 반경 < ARC_R_MAX 연속 구간
    w = int(CURV_W / 0.25)
    R = [math.inf] * len(dense)
    for i in range(w, len(dense) - w):
        R[i] = radius3(dense[i - w], dense[i], dense[i + w])
    arcs, cur = [], None
    for i, r in enumerate(R):
        if r < ARC_R_MAX and cur is None:
            cur = [i, i]
        elif r < ARC_R_MAX:
            cur[1] = i
        elif cur is not None:
            arcs.append(cur)
            cur = None
    if cur:
        arcs.append(cur)
    arcs = [c for c in arcs if dc[c[1]] - dc[c[0]] >= 3.0]
    # 궤적 (Gazebo) → FRAME xy
    csvs = sorted(a.run.glob("corner_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)   # 가장 최근 것
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
    vs = track_speeds(rows)
    # 진행 거리 s (단조 탐색: 앞쪽 40 m 창)
    S, D = [], []
    lo = 0
    for r in rows:
        d, s = project(dense, dc, r["x"], r["y"], lo=max(0, lo - 40), hi=lo + 400)
        S.append(s)
        D.append(d)
        lo = max(lo, int(s / 0.25))
    # PX4 실린 속도 (ulog)
    carried = []
    us = a.run / "ulog_speed.csv"
    if us.exists():
        with open(us, newline="") as f:
            for r in csv.DictReader(f):
                if r["kind"] == "triplet" and r["lat"] not in ("nan", "") and float(r["cruising_speed"]) > 0:
                    x, y = GZ_FRAME.to_xy(float(r["lat"]), float(r["lon"]))
                    lat, lon = GZ_FRAME.to_ll(x, y)
                    carried.append({"xy": FRAME.to_xy(lat, lon), "v": float(r["cruising_speed"])})
    # 허용치 근거:
    #  σ_meas = 출발 전 정차 구간(첫 이동 0.3 m/s 전) 궤적 속도의 표준편차 — 계측(차분) 잡음
    #  e95 = 정속 표본(|가속| < 0.3 m/s², 계획선 3 m 안, 원호 밖, 출발 램프 뒤)에서 (실제 − 그 구간에 실린 항목 속도) 의 95 백분위 — PX4 추종 오차
    item_s = [project(dense, dc, x, y)[1] for (x, y), _ in items]
    T = [r["sim_t"] for r in rows]
    acc = [0.0] * len(rows)
    for i in range(len(rows)):
        j, k = max(0, i - 10), min(len(rows) - 1, i + 10)
        acc[i] = (vs[k] - vs[j]) / (T[k] - T[j]) if T[k] > T[j] else 0.0
    mv = next((i for i, x in enumerate(vs) if x >= 0.3), len(vs))
    still = vs[:max(0, mv - 10)]
    sig = (math.sqrt(sum((x - sum(still) / len(still)) ** 2 for x in still) / len(still)) if len(still) >= 10 else None)
    in_arc = lambda s: any(dc[c[0]] - 3 <= s <= dc[c[1]] + 3 for c in arcs)
    exc = []
    for i in range(len(rows)):
        if S[i] < 15.0 or D[i] >= 3.0 or abs(acc[i]) >= 0.3 or in_arc(S[i]):
            continue
        k = next((n for n, si in enumerate(item_s) if si >= S[i]), None)
        if k is not None:
            exc.append(vs[i] - items[k][1])
    exc.sort()
    e95 = exc[int(0.95 * (len(exc) - 1))] if len(exc) >= 20 else None
    noise = [sig] if sig is not None else []
    tol = max(0.15, (e95 or 0.0) + 2 * (sig or 0.0))
    reach_s = max(S) if S else 0.0
    out = {"run": a.run.name, "plan": a.plan.name, "lat_accel": a.lat, "eta_sec": plan.get("eta_sec"),
           "tolerance": {"value_mps": round(tol, 3), "rule": "max(0.15, e95 + 2*sigma_meas)",
                         "e95_steady_excess_mps": None if e95 is None else round(e95, 3),
                         "sigma_meas_mps": None if sig is None else round(sig, 3), "n_samples": len(exc),
                         "segments": len(noise)},
           "corners": []}
    for n, (i0, i1) in enumerate(arcs):
        s0, s1 = dc[i0], dc[i1]
        rmin = min(R[i0:i1 + 1])
        vc = math.sqrt(a.lat * rmin)
        pv_arc = min(pv[k] for k in range(len(pxy)) if s0 - 1 <= pc[k] <= s1 + 1) if any(s0 - 1 <= pc[k] <= s1 + 1 for k in range(len(pxy))) else None
        it_arc = [v for (xy, v), s in zip(items, item_s) if s0 - 3 <= s <= s1 + 3]
        ca_arc = [c["v"] for c in carried if s0 - 3 <= project(dense, dc, *c["xy"])[1] <= s1 + 3]
        ent = [vs[i] for i in range(len(rows)) if s0 - ENTRY_LOOK_M <= S[i] <= s0 and D[i] < 5.0]
        inn = [vs[i] for i in range(len(rows)) if s0 <= S[i] <= s1 and D[i] < 5.0]
        dev = [D[i] for i in range(len(rows)) if s0 - 5 <= S[i] <= s1 + 10]
        c = {"corner": n + 1, "s_m": [round(s0, 1), round(s1, 1)], "r_min_m": round(rmin, 2), "v_curve_mps": round(vc, 2),
             "plan_v_min_arc": pv_arc, "item_speeds_arc": it_arc, "px4_carried_arc": ca_arc,
             "reached": reach_s >= s1,
             "v_entry_max_mps": round(max(ent), 2) if ent else None,
             "v_arc_max_mps": round(max(inn), 2) if inn else None,
             "track_dev_max_m": round(max(dev), 2) if dev else None}
        # 정점(최소 반경 지점 ±2 m) 실제 속도 vs 곡선 속도, 원호 전 구간 실제 속도 vs 같은 위치 계획 속도(가감속 반영)
        ia = min(range(i0, i1 + 1), key=lambda i: R[i])
        sa = dc[ia]
        apex = [vs[i] for i in range(len(rows)) if abs(S[i] - sa) <= 2.0 and D[i] < 5.0]
        def plan_at(s):
            k = next((n for n in range(1, len(pc)) if pc[n] >= s), len(pc) - 1)
            return pv[k - 1] + (pv[k] - pv[k - 1]) * ((s - pc[k - 1]) / (pc[k] - pc[k - 1]) if pc[k] > pc[k - 1] else 0.0)
        over = [vs[i] - plan_at(S[i]) for i in range(len(rows)) if s0 <= S[i] <= s1 and D[i] < 5.0]
        c["s_apex_m"] = round(sa, 1)
        c["v_apex_max_mps"] = round(max(apex), 2) if apex else None
        c["arc_max_over_plan_mps"] = round(max(over), 2) if over else None
        c["entry_ok"] = None if not ent else max(ent) <= vc + tol
        c["apex_ok"] = None if not apex else max(apex) <= vc + tol
        c["arc_vs_plan_ok"] = None if not over else max(over) <= tol
        out["corners"].append(c)
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
    print(json.dumps(out, ensure_ascii=False, indent=1))
    (a.run / "judge_corner.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
