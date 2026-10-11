# -*- coding: utf-8 -*-
"""정차 출발 도로 선택 (2026-10-11 Gazebo c23 소방차 갇힘) — vehicle.choose_start_dirpos.

교차로 495011 에서 2.5 m 떨어져 회전 도중 정차 — 지나온 도로 682501652 (2.6 m, 교차로까지 2.8 m, 방향 차 39°) 와
다음 도로 682501875 (2.7 m, 방향 차 47°). 위치 오차 0.2 m 로 지나온 도로 끝이 출발로 잡히면 교차로 회전을 계획하지 못해
복귀·출동이 모두 거절됐다. 순서: 직전 주행 경로(도로 연결) → 진행 방위(60°). 거리 차 1 m 안, 교차로 15 m 안, 정차 중만.
경계(1 m·60°·주행 중·교차로 먼 곳)와 평행 도로·교차로 통과 뒤·방위 오차는 작은 합성 도로망으로 확인한다.
"""

import asyncio
import dataclasses
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from interfaces.exec_store import ExecStore
from ugv import config
from ugv.clock import ManualClock
from ugv.drive_graph import DirPos, DriveGraph
from ugv.fire import StaticFireSource
from ugv.geo import FRAME
from ugv.roads import RoadPos
from ugv.server import Fleet
from ugv.tests.test_stage3_drive import NET
from ugv.vehicle import choose_start_dirpos

STOP_LL = (38.0612694, 128.1675169)
HEADING = 173.2


# ---------------------------------------------------------------- 실제 도로망 (c23 위치)
def _fire1(tmp_path, x, y):
    fl = json.loads((Path(config.UGV_DIR) / "fleet_ab.json").read_text(encoding="utf-8"))
    cfg = [{**next(c for c in fl if c["resource_id"] == "A-fire1"), "driver": "sim",
            "initial": dict(zip(("lat", "lon"), FRAME.to_ll(x, y)), heading_deg=HEADING)}]
    fleet = Fleet(cfg, net=NET, fire_source=StaticFireSource([], "T", explicit=True), clock=ManualClock(),
                  store=ExecStore(tmp_path / "t.json"))
    a = fleet.vehicles["A-fire1"]
    orig = a.driver.telemetry
    a.driver.telemetry = lambda: dataclasses.replace(orig(), x=x, y=y, heading_deg=HEADING, speed_mps=0.0)
    return a


@pytest.mark.parametrize("dx,dy", [(0.0, 0.0), (0.0, 0.2), (0.0, -0.2), (0.2, 0.0), (-0.2, 0.0)])
def test_c23_stop_position_with_offsets_starts_on_next_road(tmp_path, dx, dy):
    x0, y0 = FRAME.to_xy(*STOP_LL)
    x, y = x0 + dx, y0 + dy
    a = _fire1(tmp_path, x, y)
    st, _, err = a.here_state()
    assert err is None and (st.road_id, st.toward) == ("682501875", "495009") and a.graph.ahead_m(st) > 100.0
    acc = a.access
    r = asyncio.run(a.evaluate({"task_id": "H", "decision_id": "D", "target_node": f"RP:{acc.road_id}:{acc.s:.1f}"}))
    assert r["verdict"] == "ACCEPT", r
    # 출동 (c23 V4 목표와 같은 방식: 거점 기준 오프셋)
    t = FRAME.to_ll(acc.x + 1800, acc.y + 1500)
    r = asyncio.run(a.evaluate({"task_id": "G", "decision_id": "D2", "target": {"lat": t[0], "lon": t[1]}}))
    assert r["verdict"] == "ACCEPT", r


def test_c23_position_route_overrides_heading():
    """직전 경로가 875 → 652 (교차로 495011 을 지나 652 로, 495010 방향)이면 진행 방위와 달라도 경로를 따른다."""
    x, y = FRAME.to_xy(*STOP_LL)
    y += 0.2
    p875, p652 = NET.at("682501875", 90.0), NET.at("682501652", 40.0)
    route = SimpleNamespace(legs=[("682501875", "495009", "495011"), ("682501652", "495011", "495010")],
                            pts=[(p875.x, p875.y), NET.nodes["495011"], (p652.x, p652.y)])
    st = choose_start_dirpos(NET, DriveGraph(NET), x, y, HEADING, 0.0, route)
    assert (st.road_id, st.toward) == ("682501652", "495010")


# ---------------------------------------------------------------- 합성 도로망 (경계)
class _Road:
    def __init__(self, rid, a, b, p, q):
        self.road_id, self.a, self.b, self.p, self.q = rid, a, b, p, q
        self.length = math.dist(p, q)


class _Net:
    def __init__(self, roads):
        self.roads = {r.road_id: r for r in roads}

    def at(self, rid, s):
        r = self.roads[rid]
        t = max(0.0, min(1.0, s / r.length))
        x, y = r.p[0] + t * (r.q[0] - r.p[0]), r.p[1] + t * (r.q[1] - r.p[1])
        return RoadPos(rid, t * r.length, x, y, 0.0)

    def on_road(self, rid, x, y):
        r = self.roads[rid]
        dx, dy = r.q[0] - r.p[0], r.q[1] - r.p[1]
        t = max(0.0, min(1.0, ((x - r.p[0]) * dx + (y - r.p[1]) * dy) / (dx * dx + dy * dy)))
        px, py = r.p[0] + t * dx, r.p[1] + t * dy
        return RoadPos(rid, t * r.length, px, py, math.hypot(x - px, y - py))

    def near(self, x, y, m):
        out = {}
        for rid in self.roads:
            q = self.on_road(rid, x, y)
            if q.dist <= m:
                out[rid] = q.dist
        return out

    def snap(self, x, y):
        return min((self.on_road(rid, x, y) for rid in self.roads), key=lambda q: q.dist)


class _Graph:
    def __init__(self, net):
        self.net = net

    def dirpos(self, pos, hd):
        r = self.net.roads[pos.road_id]
        tx, ty = r.q[0] - r.p[0], r.q[1] - r.p[1]
        hx, hy = math.sin(math.radians(hd)), math.cos(math.radians(hd))
        return DirPos(pos, r.b if tx * hx + ty * hy >= 0 else r.a)

    def ahead_m(self, dp):
        r = self.net.roads[dp.road_id]
        return r.length - dp.pos.s if dp.toward == r.b else dp.pos.s

    def oneway_ok(self, rid, frm):
        return True

    def other(self, rid, node):
        r = self.net.roads[rid]
        return r.a if node == r.b else r.b


# 지나온 도로 A: 서 → 교차로 J (0,0). 동쪽(90°)으로 향하던 차가 J 3 m 앞에 정차
ROAD_A = _Road("A", "W", "J", (-100.0, 0.0), (0.0, 0.0))
ROAD_N = _Road("N", "J", "NN", (0.0, 0.0), (0.0, 100.0))           # J 에서 북쪽으로 (회전)
ROUTE_AN = SimpleNamespace(legs=[("A", "W", "J"), ("N", "J", "NN")], pts=[(-100.0, 0.0), (0.0, 0.0), (0.0, 100.0)])


def _pick(roads, x, y, hd=90.0, v=0.0, route=None):
    net = _Net(roads)
    return choose_start_dirpos(net, _Graph(net), x, y, hd, v, route)


@pytest.mark.parametrize("gap,expect", [(0.99, "B"), (1.0, "B"), (1.01, "A")])
def test_tie_distance_boundary(gap, expect):
    """가까운 평행 도로 B (동쪽으로 길게): 거리 차 1 m 안일 때만 다른 해석으로 본다 (경로 정보 없음)."""
    b = _Road("B", "BW", "BE", (-100.0, 0.4 + 0.4 + gap), (100.0, 0.4 + 0.4 + gap))
    st = _pick([ROAD_A, b], -3.0, 0.4)
    assert st.road_id == expect


@pytest.mark.parametrize("ang,expect", [(55.0, "C"), (59.0, "C"), (61.0, "A"), (65.0, "A")])
def test_heading_alignment_boundary(ang, expect):
    """차 위치 근처를 지나는 도로 C 가 진행 방위와 ang 도 어긋남: 60° 안일 때만."""
    x, y = -3.0, 0.3
    th = math.radians(ang)                                            # 동쪽에서 반시계 ang
    c = (x - 0.5 * math.sin(th), y + 0.5 * math.cos(th))              # C 는 차에서 수직 0.5 m (A 0.3 m 와 거리 차 1 m 안)
    p = (c[0] - 50 * math.cos(th), c[1] - 50 * math.sin(th))
    q = (c[0] + 50 * math.cos(th), c[1] + 50 * math.sin(th))
    st = _pick([ROAD_A, _Road("C", "C0", "C1", p, q)], x, y)
    assert st.road_id == expect


def test_parallel_road_not_chosen_when_previous_route_says_otherwise():
    """평행 도로 B 가 거리 차 1 m 안이어도 직전 경로가 A → N 이면 B 를 고르지 않는다 (경로 우선 — A, 교차로 회전은 계획기가)."""
    b = _Road("B", "BW", "BE", (-100.0, 1.2), (100.0, 1.2))
    st = _pick([ROAD_A, ROAD_N, b], -3.0, 0.4, route=ROUTE_AN)
    assert (st.road_id, st.toward) == ("A", "J")


def test_vehicle_already_past_junction_keeps_next_road():
    """교차로를 지나 N 위 (N 이 가장 가깝고 앞 거리 충분) → 그대로 N."""
    st = _pick([ROAD_A, ROAD_N], 0.3, 4.0, hd=10.0, route=ROUTE_AN)
    assert (st.road_id, st.toward) == ("N", "NN")


def test_route_picks_next_leg_at_junction():
    """회전 도중 정차 (A 끝·N 시작 사이, 거리 차 1 m 안) → 직전 경로의 다음 구간 N. 정차 방위가 틀어져도 같다."""
    for hd in (30.0, 45.0, 60.0, 100.0):
        st = _pick([ROAD_A, ROAD_N], -0.8, 0.9, hd=hd, route=ROUTE_AN)
        assert (st.road_id, st.toward) == ("N", "NN")


def test_slightly_wrong_standstill_heading_same_result():
    b = _Road("B", "BW", "BE", (-100.0, 1.2), (100.0, 1.2))
    assert _pick([ROAD_A, b], -3.0, 0.4, hd=80.0).road_id == _pick([ROAD_A, b], -3.0, 0.4, hd=100.0).road_id == "B"


def test_moving_or_far_from_junction_unchanged():
    b = _Road("B", "BW", "BE", (-100.0, 1.2), (100.0, 1.2))
    assert _pick([ROAD_A, b], -3.0, 0.4, v=1.0).road_id == "A"            # 주행 중: 예전 그대로
    assert _pick([ROAD_A, b], -30.0, 0.4).road_id == "A"                  # 교차로 30 m 앞: 예전 그대로


def test_start_road_unchanged_away_from_junction(tmp_path):
    fleet = Fleet([{**c, "driver": "sim"} for c in json.loads((Path(config.UGV_DIR) / "fleet_ab.json").read_text(encoding="utf-8"))],
                  net=NET, fire_source=StaticFireSource([], "T", explicit=True), clock=ManualClock(), store=ExecStore(tmp_path / "t.json"))
    for a in fleet.vehicles.values():
        tel = a.driver.telemetry()
        old = a.graph.dirpos(NET.snap(tel.x, tel.y), tel.heading_deg)
        st, _, _ = a.here_state()
        if a.graph.ahead_m(old) >= 15.0:
            assert (st.road_id, st.toward) == (old.road_id, old.toward)
