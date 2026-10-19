# -*- coding: utf-8 -*-
"""생성 원호 곡선 속도 상한(roads._route_arcs)·마지막 구간 도착 반경 창 — 2026-10-19 교차로 곡률판정·속도계획 검증보완계획 §4.

앞뒤 5 m 창 세 점 원은 원호 끝 창 길이 안에서 직선을 섞어 곡률을 작게 본다. 반쪽 창 보조(CURVE_SIDE_R_M = 25 m)에 걸리지 않는
반경 25~40 m 원호는 원호 끝 계획 속도가 곡선 속도보다 1.1~1.3 m/s 빨랐고, 25 m 경계에서 불연속이었다 (cutoff 25: R 25.0 +0.29,
25.1 +1.27 m/s). 선형 다듬기가 그린 원호는 반경·접점을 알므로 원호 전 구간에 √(횡가속 × R) 를 직접 건다.
"""
import math
from types import SimpleNamespace

import pytest

from ugv import config
from ugv.drivers.px4 import ACCEPT_M
from ugv.profiles import PROFILES
from ugv.roads import _route_arcs, plan_speeds


def _route(R=30.0, turn_deg=90.0, lead=60.0, tail=60.0, step=None, kind="junction", side=-1, more=None):
    """직선 lead → 반경 R 원호 (생성 원호처럼 min(2, √(8R·0.02)) 간격, side −1 = 오른쪽) → 직선 tail (5 m 간격 원래 점).
    route.arcs 에 생성 정보 (i0, i1, R, cx, cy, 회전각, 종류). more: 이어 붙일 두 번째 원호 (R2, deg2, side2) — S 자 연속 원호"""
    step = step or min(2.0, math.sqrt(8 * R * 0.02))
    pts = [(-lead + k * 5.0, 0.0) for k in range(int(lead / 5.0))]
    arcs = []

    def add_arc(p0, h0, R, deg, sg):
        th = math.radians(deg)
        C = (p0[0] - sg * R * math.sin(h0), p0[1] + sg * R * math.cos(h0))
        a0 = math.atan2(p0[1] - C[1], p0[0] - C[0])
        n = max(2, math.ceil(R * th / step))
        i0 = len(pts) if not pts or math.dist(pts[-1], p0) > 1e-9 else len(pts) - 1
        q = [(C[0] + R * math.cos(a0 + sg * th * k / n), C[1] + R * math.sin(a0 + sg * th * k / n)) for k in range(n + 1)]
        if i0 == len(pts) - 1:
            q = q[1:]
        pts.extend(q)
        arcs.append((i0, len(pts) - 1, R, C[0], C[1], th, kind))
        return pts[-1], h0 + sg * th
    end, h = add_arc((0.0, 0.0), 0.0, R, turn_deg, side)
    if more:
        end, h = add_arc(end, h, more[0], more[1], more[2])
    pts += [(end[0] + k * 5.0 * math.cos(h), end[1] + k * 5.0 * math.sin(h)) for k in range(1, int(tail / 5.0) + 1)]
    return SimpleNamespace(pts=pts, vlim=[20.0] * len(pts), arcs=arcs)


def _on_arc(sp, a):
    s0, s1 = a[0], a[1]
    return [sp.v[k] for k in range(len(sp.v)) if s0 - 1e-6 <= sp.cum[k] <= s1 + 1e-6]


@pytest.mark.parametrize("R", [8.41, 10.28, 24.9, 25.0, 25.1, 30.0, 39.9, 40.0, 40.1, 50.0])
def test_whole_generated_arc_le_curve_speed_and_not_lower(R):
    """원호 전 구간(접점 포함) 계획 ≤ √(a·R), 그리고 원호 안을 쓸데없이 낮추지 않는다 (≥ √(a·R) − 0.05). 원호에 걸리는 PX4 구간
    속도(앞 지점 도착 반경부터 적용)도 곡선 속도 이하."""
    lat = 1.0
    sp = plan_speeds(_route(R), 0.0, lat_accel=lat)
    vc = math.sqrt(lat * R)
    assert len(sp.arcs) == 1
    s0, s1 = sp.arcs[0][:2]
    on = _on_arc(sp, sp.arcs[0])
    assert max(on) <= vc + 1e-9, (R, max(on), vc)
    assert min(on) >= vc - 0.05, (R, min(on), vc)
    pos = {(round(x, 6), round(y, 6)): k for k, (x, y) in enumerate(sp.pts)}
    idx = [pos[(round(x, 6), round(y, 6))] for x, y, _ in sp.items_on_path]
    for n in range(1, len(idx)):
        if sp.cum[idx[n - 1]] - ACCEPT_M <= s1 and sp.cum[idx[n]] >= s0:
            assert sp.items[n][2] <= vc + 0.01, (R, n, sp.items[n][2], vc)


def test_no_jump_at_old_cutoffs():
    """반경 24.9/25.0/25.1, 39.9/40.0/40.1 m 에서 원호 최고 계획 속도 차이가 반경 차이만큼만 (예전 cutoff 25 는 25.0→25.1 에 +0.97 m/s)."""
    def vmax(R):
        sp = plan_speeds(_route(R), 0.0, lat_accel=1.0)
        return max(_on_arc(sp, sp.arcs[0]))
    for a, b in ((24.9, 25.0), (25.0, 25.1), (39.9, 40.0), (40.0, 40.1)):
        assert abs(vmax(b) - vmax(a)) <= abs(math.sqrt(b) - math.sqrt(a)) + 0.02, (a, b, vmax(a), vmax(b))


def test_without_arc_info_old_window_behaviour_kept():
    """생성 정보가 없거나(정지·대기 경로) 원 위에 없는 정보(경로가 바뀜)면 상한을 걸지 않는다 — 창 곡률만 (예전과 같다)"""
    r = _route(30.0)
    base = plan_speeds(SimpleNamespace(pts=r.pts, vlim=r.vlim), 0.0, lat_accel=1.0)
    assert not base.arcs
    i0, i1, R, cx, cy, D, kind = r.arcs[0]
    bad = SimpleNamespace(pts=r.pts, vlim=r.vlim, arcs=[(i0, i1, R, cx + 1.0, cy, D, kind)])
    sp = plan_speeds(bad, 0.0, lat_accel=1.0)
    assert not sp.arcs and sp.v == base.v
    # 창 곡률만이면 반경 30 m 원호 끝이 곡선 속도보다 빠르다 (이 수정이 다루는 결함)
    s0, s1 = plan_speeds(r, 0.0, lat_accel=1.0).arcs[0][:2]
    assert max(base.v[k] for k in range(len(base.v)) if s0 <= base.cum[k] <= s1) > math.sqrt(30.0) + 0.5


def test_s_curve_consecutive_arcs_each_capped():
    """짧은 연속 원호·방향 전환 (오른쪽 R 12 → 왼쪽 R 30): 두 원호 모두 자기 곡선 속도 이하, 접점 공유점은 작은 쪽"""
    sp = plan_speeds(_route(12.0, 60.0, more=(30.0, 45.0, +1)), 0.0, lat_accel=1.0)
    assert len(sp.arcs) == 2
    for a in sp.arcs:
        assert max(_on_arc(sp, a)) <= math.sqrt(a[2]) + 1e-9, a


def test_bend_arc_short_spread_over_window_long_exact():
    """일반 꺾인 점 원호(bend): 길이 ≥ 2w 면 R 그대로, 짧으면 같은 방향 변화를 2w 에 걸쳐 본 반경 (도로 좌표 꺾임마다 급감속 방지)"""
    w = config.CURVE_WINDOW_M
    long_r = _route(50.0, 30.0, kind="bend")                 # 길이 26 m
    (_, _, R, rc, _), = _route_arcs(long_r, w)
    assert rc == R
    short = _route(50.0, 4.0, kind="bend")                    # 길이 3.5 m
    (_, _, R, rc, _), = _route_arcs(short, w)
    assert rc == pytest.approx(R * 2 * w / (R * math.radians(4.0)))
    # 같은 짧은 원호가 교차로 원호면 R 그대로
    (_, _, R, rc, _), = _route_arcs(_route(50.0, 4.0, kind="junction"), w)
    assert rc == R


def test_profile_lat_accel_and_accel_kept_for_firetruck():
    """소방차 프로필(횡가속 1.2, 가속 1.2, 감속 1.5): 원호 상한 = √(1.2·R), 원호 뒤 가속이 프로필 가속 한계 안"""
    p = PROFILES["adair_firetruck"]
    for R in (12.0, 30.0):
        sp = plan_speeds(_route(R), 0.0, profile=p)
        assert max(_on_arc(sp, sp.arcs[0])) <= math.sqrt(p.lat_accel_mps2 * R) + 1e-9
        for k in range(1, len(sp.v)):
            ds = sp.cum[k] - sp.cum[k - 1]
            assert sp.v[k] ** 2 <= sp.v[k - 1] ** 2 + 2 * p.accel_mps2 * ds + 1e-6
            assert sp.v[k - 1] ** 2 <= sp.v[k] ** 2 + 2 * p.decel_mps2 * ds + 1e-6


# ---------------------------------------------------------------------- 마지막(도착) 구간
def _line(xs, vlim=None):
    pts = [(float(x), 0.0) for x in xs]
    return SimpleNamespace(pts=pts, vlim=vlim or [20.0] * len(pts))


def test_final_leg_without_inner_samples_uses_lead_window_not_1mps():
    """앞 지점 바로 다음이 도착점(구간 안 표본 없음)이면 예전에는 1 m/s — 도착 반경 창의 계획 속도를 쓴다 (느린 꼬리 방지)"""
    # 0~100 m 직선 5 m 간격, 95 m 에서 꺾이게 해 앞 지점을 도착점 바로 앞에 둔다
    pts = [(5.0 * k, 0.0) for k in range(20)] + [(95.0 + 4.0 * math.cos(math.radians(-20)), 4.0 * math.sin(math.radians(-20)))]
    sp = plan_speeds(SimpleNamespace(pts=pts, vlim=[20.0] * len(pts)), 0.0, lat_accel=1.0)
    on = sp.items_on_path
    assert on[-2][:2] == pts[-2], on[-3:]                      # 앞 지점 = 도착점 바로 앞 점
    k_prev = len(sp.pts) - 2
    lead = [sp.v[k] for k in range(len(sp.pts) - 1) if sp.cum[k_prev] - ACCEPT_M <= sp.cum[k] <= sp.cum[k_prev]]
    assert on[-1][2] == max(math.floor(min(lead) * 100) / 100, 1.0)
    assert on[-1][2] > 1.0


def test_final_leg_already_slow_kept_and_long_final_not_1mps():
    """이미 느린 마지막 구간은 그 속도, 긴 마지막 직선은 도착점 0 때문에 1 m/s 가 되지 않는다"""
    sp = plan_speeds(_line(range(0, 121, 5), vlim=[2.0 if x >= 60 else 20.0 for x in range(0, 121, 5)]), 0.0, lat_accel=1.0)
    assert sp.items_on_path[-1][2] <= 2.0 + 1e-9 and sp.items_on_path[-1][2] > 1.0
    sp = plan_speeds(_line(range(0, 201, 5)), 0.0, lat_accel=1.0)
    assert sp.items_on_path[-1][2] > 1.0


def test_final_leg_lead_window_overlapping_previous_items():
    """앞 지점들 간격이 도착 반경보다 짧아 창이 그 앞 지점까지 겹쳐도 구간 속도 = 창 안 최소 (빠뜨린 표본 없음)"""
    xs = list(range(0, 41)) + [41.0, 42.0, 43.0, 44.5]
    pts = [(float(x), 0.0) for x in xs[:41]] + [(41.0, -0.3), (42.0, -0.9), (43.0, -1.8), (44.0, -3.0)]
    vlim = [20.0] * len(pts)
    sp = plan_speeds(SimpleNamespace(pts=pts, vlim=vlim), 0.0, lat_accel=1.0)
    idx = []
    for x, y, _ in sp.items_on_path:
        idx.append(next(k for k, p in enumerate(sp.pts) if math.dist(p, (x, y)) < 1e-9))
    for n in range(1, len(idx)):
        lo_s = sp.cum[idx[n - 1]] - ACCEPT_M
        end = idx[n] if n == len(idx) - 1 else idx[n] + 1
        want = [sp.v[k] for k in range(len(sp.v)) if lo_s <= sp.cum[k] and k < end and sp.cum[k] >= config.ITEM_FIRST_MIN_M]
        assert sp.items_on_path[n][2] <= max(math.floor(min(want) * 100) / 100, 1.0) + 1e-9


def test_sent_items_move_less_than_lead_so_acceptance_covered():
    """곡선 보정으로 옮긴 전송 지점은 계획선 위 지점에서 ITEM_CURVE_COMP_MAX_M 이하로만 옆으로 움직인다 → 도착 반경 원이 계획선과
    만나는 곳은 지점에서 √(ACCEPT² − 옮김²) ≤ ACCEPT_M 앞 — 도착 반경 창(ITEM_SPEED_LEAD_M = ACCEPT_M)이 덮는다. 마지막 지점은 옮기지 않는다"""
    assert config.ITEM_SPEED_LEAD_M == ACCEPT_M
    sp = plan_speeds(_route(10.28), 0.0, lat_accel=1.0)
    for (x, y, v), (ox, oy, ov) in zip(sp.items, sp.items_on_path):
        assert math.dist((x, y), (ox, oy)) <= config.ITEM_CURVE_COMP_MAX_M + 1e-9 and v == ov
    assert sp.items[-1][:2] == sp.items_on_path[-1][:2]


def test_real_routes_arc_info_matches_final_geometry():
    """실제 도로망 경로: _smooth 가 넘긴 원호 정보의 점이 모두 그 원 위(≤ 0.03 m), 계획이 원호 전 구간 ≤ √(a·R)"""
    import random
    from ugv.drive_graph import access_point
    from ugv.roads import RoadNetwork
    net = RoadNetwork()
    g = net.graph
    acc = access_point(net, "A")
    tree = g.search(g.dirpos(acc[0], acc[1]), 0.0)
    rng = random.Random(7)
    rids = sorted(r for r in net.roads if (r, net.roads[r].b) in tree["dist"])
    rng.shuffle(rids)
    n_routes = n_arcs = 0
    for rid in rids[:40]:
        r = net.roads[rid]
        p = net.at(rid, r.length * 0.5)
        arrs = g.arrivals(tree, p)
        if not arrs:
            continue
        route = g.build_route(tree, p, min(arrs, key=lambda a: a.time_s))
        n_routes += 1
        for i0, i1, R, cx, cy, D, kind in route.arcs:
            n_arcs += 1
            assert max(abs(math.dist(route.pts[k], (cx, cy)) - R) for k in range(i0, i1 + 1)) <= 0.03
        sp = plan_speeds(route, profile=g.p)
        for a in sp.arcs:
            assert max(_on_arc(sp, a)) <= math.sqrt(g.p.lat_accel_mps2 * a[3]) + 1e-9
    assert n_routes >= 10 and n_arcs >= 10, (n_routes, n_arcs)
