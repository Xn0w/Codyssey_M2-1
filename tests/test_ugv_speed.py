# -*- coding: utf-8 -*-
"""차량 속도 — PX4 는 max_speed_mps, sim 은 sim_speed_mps(상한 60 km/h) / 도로 속도는 제한속도를 하한 50 km/h 로 올린 뒤
차량 속도로 자르고, 혼잡 배율로 나눈다 (총괄 브랜치 결정 2026-10-07 과 같은 규칙).

실행 (저장소 루트):  python -m pytest tests/test_ugv_speed.py -q
"""

from ugv import config, graph_gpkg
from ugv.fleet import GroundFleet
from ugv.models import Road

V = 60 / 3.6


def _cfg(rid):
    return next(r for r in config.RESOURCES if r["resource_id"] == rid)


def test_sim_speed_only_in_sim(monkeypatch):
    fe, ugv = _cfg("A-fire1"), _cfg("A-ugv1")
    fleet = GroundFleet(use_px4=False, graph_data=graph_gpkg, time_scale=100)
    assert fleet.agents["A-fire1"].max_speed_mps == fe["sim_speed_mps"] == V > fe["max_speed_mps"]
    assert fleet.agents["A-fire1"].driver.speed_mps == fe["sim_speed_mps"]       # 주행과 ETA 가 같은 값
    assert fleet.agents["A-ugv1"].max_speed_mps == ugv["sim_speed_mps"]          # UGV 도 sim 에서는 같은 속도
    assert all(r["sim_speed_mps"] == V for r in config.RESOURCES)
    # PX4 로 달리는 차는 sim_speed_mps 를 무시한다 (Gazebo r1_rover 속도)
    monkeypatch.setattr(config, "PX4_RESOURCES", ["A-fire1"])
    assert fleet._speed(fe, use_px4=True) == fe["max_speed_mps"]
    assert fleet._speed(fe, use_px4=False) == fe["sim_speed_mps"]


def test_road_speed_floor_cap_and_congestion():
    r = Road(road_id="x", node_a="a", node_b="b", distance_m=1000.0, base_time_s=120.0, speed_kmh=30)
    assert abs(r.speed_mps(V) - 50 / 3.6) < 1e-9             # 시군도 30 km/h → 하한 50 km/h
    r.speed_kmh = 80
    assert abs(r.speed_mps(V) - V) < 1e-9                    # 80 km/h 도로 → 차량 상한 60 km/h
    r.speed_kmh = 30; r.congestion = 2.0
    assert abs(r.speed_mps(V) - 50 / 3.6 / 2) < 1e-9         # 혼잡은 나눈다
    assert abs(r.travel_s(V) - 1000 / (50 / 3.6 / 2)) < 1e-6
    r.congestion = 1.0
    assert r.speed_mps(2.0) == 2.0                           # PX4 2.0 m/s 는 하한보다 작아 그대로
    assert abs(r.speed_mps() - 30 / 3.6) < 1e-9              # 차량 속도가 없으면(시연 도로망) 도로 속도
