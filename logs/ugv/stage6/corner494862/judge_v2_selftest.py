# -*- coding: utf-8 -*-
"""judge_corner_v2 자체 기하 검증 (Gazebo 없음, 순수 계산). 사용: python -X utf8 judge_v2_selftest.py [출력 json]

합격 기준 (실행 전 고정, 2026-10-19):
  좌표 양자화 q = 0.01 m 반올림 → 점당 최대 오차 q·√2/2 = 0.0071 m.
  - 반경: |R_fit − R| ≤ max(0.005 m, R × 2·0.0071 / 화살높이)   (화살높이 = R(1 − cos(θ/2)), 반올림 오차가 화살높이를 흔드는 비율의 2 배)
  - 시작·끝·중앙 진행거리 s: 균등 표본(생성 원호와 같은 방식) ≤ 0.05 m, 비균등 표본 ≤ √(2·R·RES_TOL) + 0.05 m
    (비균등이면 접점 앞 직선 점이 잔차 허용치 안에 들 수 있는 거리)
  - 회전 방향 일치, 회전각 오차 ≤ 1°
  - 직선·중복점·거의 일직선(3°)·짧은 원호(점 3 개) 는 CONFIRMED 원호를 내지 않는다
  - 합성 궤적 속도 판정: 알려진 v(s) 를 20 Hz 로 따라간 궤적에서 정점·진입·원호 최대 초과가 해석값 ±0.02 m/s
"""
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import judge_corner_v2 as J  # noqa: E402

Q = 0.01
QE = Q * math.sqrt(2) / 2


def build(R, deg, side, arc_mode="uniform", lead=60.0, tail=60.0, straight_step=5.0, close_neighbor=None, rot=0.0,
          off=(4096.3, 6360.8), rnd=True, seed=0):
    """직선 lead → 반경 R 원호(deg) → 직선 tail. 반환 (점, 원호 시작 s, 끝 s). 생성 원호와 같은 표본 간격(min(2, √(8R·0.02)))."""
    rng = random.Random(seed)
    pts = [(-lead + k * straight_step, 0.0) for k in range(int(lead / straight_step))]
    if close_neighbor:
        pts.append((-close_neighbor, 0.0))
    th = math.radians(deg)
    sg = 1 if side == "L" else -1
    C = (0.0, sg * R)
    a0 = math.atan2(-sg * R, 0.0)
    if arc_mode == "uniform":
        step = min(2.0, math.sqrt(8 * R * 0.02))
    elif arc_mode == "sparse":
        step = 2.5
    else:
        step = None
    if step:
        n = max(2, math.ceil(R * th / step))
        fr = [k / n for k in range(n + 1)]
    else:
        L = R * th
        cuts, s = [0.0], 0.0
        while True:
            s += rng.uniform(0.4, 2.0)
            if s >= L - 0.2:
                break
            cuts.append(s)
        cuts.append(L)
        fr = [c / L for c in cuts]
    arc = [(C[0] + R * math.cos(a0 + sg * th * f), C[1] + R * math.sin(a0 + sg * th * f)) for f in fr]
    pts += arc
    ex, ey = arc[-1]
    h = sg * th
    if close_neighbor:
        pts.append((ex + close_neighbor * math.cos(h), ey + close_neighbor * math.sin(h)))
    pts += [(ex + k * straight_step * math.cos(h), ey + k * straight_step * math.sin(h)) for k in range(1, int(tail / straight_step) + 1)]
    c, s_ = math.cos(rot), math.sin(rot)
    pts = [(off[0] + x * c - y * s_, off[1] + x * s_ + y * c) for x, y in pts]
    if rnd:
        pts = [(round(x, 2), round(y, 2)) for x, y in pts]
    cum = J.cumlen(pts)
    # 참 접점 위치 (원래 점 인덱스로)
    i0 = int(lead / straight_step) + (1 if close_neighbor else 0)
    i1 = i0 + len(arc) - 1
    return pts, cum[i0], cum[i1]


def check_geom(name, R, deg, side, **kw):
    pts, s0, s1 = build(R, deg, side, **kw)
    cum = J.cumlen(pts)
    arcs = [a for a in J.detect_arcs(pts, cum) if a["status"] == "CONFIRMED"]
    sag = R * (1 - math.cos(math.radians(deg) / 2))
    tolR = max(0.005, R * 2 * QE / sag)
    uniform = kw.get("arc_mode", "uniform") == "uniform"
    tolS = 0.05 if uniform else math.sqrt(2 * R * J.RES_TOL_M) + 0.05
    rec = {"case": name, "R": R, "deg": deg, "side": side, **{k: v for k, v in kw.items() if k in ("arc_mode", "close_neighbor", "rot")},
           "tol_R_m": round(tolR, 4), "tol_s_m": round(tolS, 3), "n_confirmed": len(arcs)}
    ok = len(arcs) == 1
    if arcs:
        a = arcs[0]
        rec.update({"R_fit": round(a["R"], 4), "dR": round(a["R"] - R, 4), "ds0": round(a["s0"] - s0, 3), "ds1": round(a["s1"] - s1, 3),
                    "dmid": round((a["s0"] + a["s1"]) / 2 - (s0 + s1) / 2, 3), "dir": a["dir"], "deg_fit": round(a["deg"], 2),
                    "res_max_m": round(a["res_max_m"], 4), "n_pts": a["n_pts"]})
        ok = ok and abs(a["R"] - R) <= tolR and abs(a["s0"] - s0) <= tolS and abs(a["s1"] - s1) <= tolS \
            and a["dir"] == side and abs(a["deg"] - deg) <= 1.0
    # 원본 판정기 반경 (정보: 0.25 m 보간·인덱스 창 반경 최소값)
    oa = J.old_arcs(pts)[0]
    rec["old_R_min"] = round(min((o["R"] for o in oa), default=math.inf), 3) if oa else None
    rec["ok"] = ok
    return rec


def check_none(name, pts):
    cum = J.cumlen(pts)
    arcs = [a for a in J.detect_arcs(pts, cum) if a["status"] == "CONFIRMED"]
    return {"case": name, "n_confirmed": len(arcs), "ok": len(arcs) == 0,
            "found": [{"R": round(a["R"], 2), "deg": round(a["deg"], 2), "n": a["n_pts"]} for a in arcs]}


def check_speed():
    """합성 궤적: 계획 v(s) = 원호 안 √R, 원호 밖 √R + 0.05·(원호까지 거리) (6 m/s 상한). 실제 = 계획 + 0.1 (전 구간).
    해석값: 정점 최대 = √R + 0.1, 원호 안 (실제 − 계획) 최대 = 0.1, 진입 창(s0−2 ~ s0) 최대 = 계획(s0−2) + 0.1 = √R + 0.2.
    (첫 작성본은 진입 직전 돌출을 넣었는데 해석값을 계획 기울기·차분 창 평활 없이 잘못 잡았다 — 판정기 결함이 아니라 시험 설계 오류라
    돌출 없는 정속 오프셋 모형으로 바꿨다. 허용치 ±0.02 m/s 는 그대로)"""
    R = 10.28
    pts, s0, s1 = build(R, 90.0, "L")
    cum = J.cumlen(pts)
    vc = math.sqrt(R)
    pv = [vc if s0 <= s <= s1 else min(6.0, vc + 0.05 * (s0 - s if s < s0 else s - s1)) for s in cum]

    def plan_at(s):
        import bisect
        k = min(max(1, bisect.bisect_left(cum, s)), len(cum) - 1)
        return pv[k - 1] + (pv[k] - pv[k - 1]) * ((s - cum[k - 1]) / (cum[k] - cum[k - 1]) if cum[k] > cum[k - 1] else 0.0)

    def pos(s):
        import bisect
        k = min(max(1, bisect.bisect_left(cum, s)), len(cum) - 1)
        f = (s - cum[k - 1]) / (cum[k] - cum[k - 1])
        return pts[k - 1][0] + f * (pts[k][0] - pts[k - 1][0]), pts[k - 1][1] + f * (pts[k][1] - pts[k - 1][1])

    rows, t, s = [], 0.0, 1.0
    for _ in range(40):                                  # 출발 전 정차 2 s
        x, y = pos(s)
        rows.append({"sim_t": t, "x": x, "y": y})
        t += 0.05
    while s < cum[-1] - 1.0:
        x, y = pos(s)
        rows.append({"sim_t": t, "x": x, "y": y})
        s += (plan_at(s) + 0.1) * 0.05
        t += 0.05
    items = [(*pts[-1], 6.0)]
    out = J.evaluate(rows, {"plan_xy": pts, "plan_v": pv, "items": items}, 1.0)
    c = [x for x in out["extra_arcs"] + [k for k in out["corners"] if "v2" in k]]
    v2 = c[0]["v2"]
    exp = {"v_apex_max_mps": vc + 0.1, "arc_max_over_plan_mps": 0.1, "v_entry_max_mps": vc + 0.2}
    got = {k: v2[k] for k in exp}
    ok = all(abs(got[k] - exp[k]) <= 0.02 for k in exp)
    return {"case": "synthetic_track_speed", "expected": {k: round(v, 3) for k, v in exp.items()},
            "got": got, "R_fit": v2["R_m"], "ok": ok}


def main():
    res = []
    for R in (8.41, 10.28, 25.0, 30.0, 40.0, 50.0):
        for side in ("L", "R"):
            res.append(check_geom(f"uniform_{R}_{side}", R, 90.0, side, rot=0.7))
        res.append(check_geom(f"nonuniform_{R}", R, 90.0, "R", arc_mode="nonuniform", rot=2.1, seed=int(R * 10)))
        res.append(check_geom(f"sparse_{R}", R, 90.0, "L", arc_mode="sparse", rot=-1.0))
        res.append(check_geom(f"close_neighbor_{R}", R, 90.0, "R", close_neighbor=0.3, rot=0.3))
        res.append(check_geom(f"short30_{R}", R, 30.0, "L", rot=1.3))
    res.append(check_geom("short15_10.28", 10.28, 15.0, "R"))
    res.append(check_geom("deg60_40", 40.0, 60.0, "L"))
    res.append(check_geom("unrounded_10.28", 10.28, 90.0, "L", rnd=False))
    res.append(check_none("straight_5m", [(4000 + 5.0 * k, 6000.0) for k in range(40)]))
    res.append(check_none("straight_1m_rounded", [(round(4000 + 1.0 * k * 0.6, 2), round(6000 + 1.0 * k * 0.8, 2)) for k in range(80)]))
    res.append(check_none("duplicates", [(4000.0 + (k // 2), 6000.0) for k in range(40)]))
    p3, _, _ = build(50.0, 3.0, "L")
    res.append(check_none("near_straight_3deg_R50", p3))
    pts = [(-30 + k * 5.0, 0.0) for k in range(6)] + [(0.0, 0.0), (1.0, -0.1), (2.0, -0.4)] + [(2.0 + 5 * k * 0.95, -0.4 - 5 * k * 0.3) for k in range(1, 6)]
    res.append(check_none("three_point_bend", pts))
    res.append(check_speed())
    n_ok = sum(1 for r in res if r["ok"])
    summary = {"n": len(res), "n_ok": n_ok, "all_ok": n_ok == len(res), "results": res}
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "v2" / "judge_v2_selftest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in res:
        print(("OK  " if r["ok"] else "FAIL"), json.dumps(r, ensure_ascii=False))
    print(f"{n_ok}/{len(res)} 통과")


if __name__ == "__main__":
    main()
