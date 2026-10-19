# -*- coding: utf-8 -*-
"""원호 상한 규칙 변형 비교 (후보 트리, 같은 120 경로·lat 1.0). 제품 코드는 바꾸지 않고 이 프로세스 안에서만 roads._route_arcs 를 바꾼다.
  Va 교차로 원호만 정확 상한 / Vb (후보) 교차로 정확 + 꺾임 원호 자기 길이 < 2w 면 펼침 / Vc 모든 생성 원호 정확 / Vd 꺾임 원호를 이어진 같은 방향 묶음 길이로 판단
독립 검출 원호(R ≤ 60)를 생성 정보와 맞춰 종류별 계획 초과(> 0.05 m/s) 수를 센다."""
import json, math, sys, collections, statistics as st
A = r"C:\Users\수다쟁이고양이들\Documents\GitHub\ADAIR"; sys.path.insert(0, A)
W = A + r"\logs\ugv\stage6\corner494862"
sys.argv = ["x", "eval", A]
exec(open(W + r"\v2\sweep\sweep120.py", encoding="utf-8").read().split('if mode == "list":')[0])
sys.path.insert(0, W)
import judge_corner_v2 as J
from ugv import roads, config
orig = roads._route_arcs
w = config.CURVE_WINDOW_M


def raw(route):
    pts = route.pts; c = [0.0]
    for p, q in zip(pts, pts[1:]):
        c.append(c[-1] + math.dist(p, q))
    out = []
    for i0, i1, R, cx, cy, D, kind in (getattr(route, "arcs", None) or []):
        sg = 1 if ((pts[i0 + 1][0] - pts[i0][0]) * (pts[i1][1] - pts[i0][1]) - (pts[i0 + 1][1] - pts[i0][1]) * (pts[i1][0] - pts[i0][0])) > 0 else -1
        out.append([c[i0], c[i1], R, D, kind, sg])
    return out


def Va(route, w):
    return [(a, b, R, R, k) for a, b, R, D, k, s in raw(route) if k == "junction"]


def Vc(route, w):
    return [(a, b, R, R, k) for a, b, R, D, k, s in raw(route)]


def Vd(route, w):
    A_ = raw(route); out = []; i = 0
    while i < len(A_):
        j = i
        if A_[i][4] == "bend":
            while j + 1 < len(A_) and A_[j + 1][4] == "bend" and A_[j + 1][5] == A_[i][5] and A_[j + 1][0] - A_[j][1] <= 0.5:
                j += 1
        grp = A_[i:j + 1]
        Lg = sum(g[2] * g[3] for g in grp)
        for a, b, R, D, k, s in grp:
            rc = R if k == "junction" or Lg >= 2 * w else max(R, 2 * w / sum(g[3] for g in grp))
            out.append((a, b, R, rc, k))
        i = j + 1
    return out


V = {"Va_junction_only": Va, "Vb_candidate": orig, "Vc_all_exact": Vc, "Vd_group_spread": Vd}
L = json.load(open(W + r"\v2\sweep\routes120.json", encoding="utf-8"))
base = {r["rid"] + r["base"]: r for r in json.load(open(W + r"\v2\sweep\eval_base_lat1.0.json", encoding="utf-8"))["rows"]}
routes = [build(rec) for rec in L]
res = {}
for name, fn in V.items():
    roads._route_arcs = fn
    eta, etai, cnt = [], [], collections.defaultdict(lambda: [0, 0, -9.0])
    for rec, route in zip(L, routes):
        sp = plan_speeds(route, profile=G.p, lat_accel=1.0)
        b = base[rec["rid"] + rec["base"]]
        eta.append(sp.eta_s / b["eta_plan"] - 1)
        on = sp.items_on_path; t, prev = 0.0, sp.pts[0]
        for x, y, v in on:
            t += math.dist(prev, (x, y)) / max(v, 1.0); prev = (x, y)
        etai.append(t / b["eta_items"] - 1)
        gen = raw(route)
        for a in [a for a in J.detect_arcs(sp.pts, sp.cum) if a["status"] == "CONFIRMED" and a["R"] <= 60]:
            m = [g for g in gen if min(g[1], a["s1"]) - max(g[0], a["s0"]) > 0.5 * (a["s1"] - a["s0"])]
            kind = m[0][4] if m else "road(none)"
            band = "R<25" if a["R"] < 25 else "R25-40" if a["R"] < 40 else "R40-60"
            o = max(sp.v[k] for k in range(a["i0"], a["i1"] + 1)) - math.sqrt(a["R"])
            c = cnt[f"{kind}/{band}"]; c[0] += 1; c[1] += o > 0.05; c[2] = max(c[2], round(o, 3))
    s = lambda r: {"mean_%": round(100 * st.mean(r), 2), "median_%": round(100 * st.median(r), 2), "p95_%": round(100 * sorted(r)[int(0.95 * 119)], 2), "max_%": round(100 * max(r), 2)}
    res[name] = {"eta_plan_vs_base": s(eta), "eta_items_vs_base": s(etai), "over_by_kind_R": {k: {"n": v[0], "n_over_0.05": v[1], "max_over": v[2]} for k, v in sorted(cnt.items())}}
    print(name, json.dumps(res[name], ensure_ascii=False))
roads._route_arcs = orig
json.dump(res, open(W + r"\v2\sweep\variants120_lat1.0.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
