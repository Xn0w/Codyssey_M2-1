# -*- coding: utf-8 -*-
"""차량 속도 — PX4 는 max_speed_mps, sim 은 sim_speed_mps(소방차) / 혼잡은 도로 속도를 나눈다.

실행 (저장소 루트):  python -m pytest tests/test_ugv_speed.py -q
"""

from ugv import config, graph_gpkg
from ugv.fleet import GroundFleet
from ugv.models import Road


def _cfg(rid):
    return next(r for r in config.RESOURCES if r["resource_id"] == rid)


def test_fire_engine_fast_only_in_sim(monkeypatch):
    fe, ugv = _cfg("A-fire1"), _cfg("A-ugv1")
    fleet = GroundFleet(use_px4=False, graph_data=graph_gpkg, time_scale=100)
    assert fleet.agents["A-fire1"].max_speed_mps == fe["sim_speed_mps"] > fe["max_speed_mps"]
    assert fleet.agents["A-fire1"].driver.speed_mps == fe["sim_speed_mps"]       # 주행과 ETA 가 같은 값
    assert fleet.agents["A-ugv1"].max_speed_mps == ugv["max_speed_mps"]          # UGV 는 sim 에서도 그대로
    # PX4 로 달리는 차는 sim_speed_mps 를 무시한다 (Gazebo r1_rover 속도)
    monkeypatch.setattr(config, "PX4_RESOURCES", ["A-fire1"])
    assert fleet._speed(fe, use_px4=True) == fe["max_speed_mps"]
    assert fleet._speed(fe, use_px4=False) == fe["sim_speed_mps"]


def test_speed_is_min_of_road_and_vehicle_divided_by_congestion():
    r = Road(road_id="x", node_a="a", node_b="b", distance_m=1000.0, base_time_s=120.0, speed_kmh=30)
    assert abs(r.speed_mps(11.0) - 30 / 3.6) < 1e-9          # 시군도 30 km/h 가 소방차 11 m/s 보다 느리다
    r.congestion = 2.0
    assert abs(r.speed_mps(11.0) - 30 / 3.6 / 2) < 1e-9
    assert abs(r.travel_s(11.0) - 1000 / (30 / 3.6 / 2)) < 1e-6
    r.speed_kmh = 60; r.congestion = 1.0
    assert r.speed_mps(11.0) == 11.0                         # 60 km/h 도로에서는 차량 속도가 정한다
