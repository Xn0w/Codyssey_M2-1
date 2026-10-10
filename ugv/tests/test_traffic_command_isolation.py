# -*- coding: utf-8 -*-
"""차량 간 충돌 판단과 차량별 명령 실행 분리 — 한 차의 명령이 늦어도 다른 차 감독이 계속된다 (2026-10-11 검토:
TrafficManager.tick 이 차량별 set_hold·clear_hold·막힘 재계획을 차례로 기다려 한 차의 지연이 모든 차의 판단을 늦췄다)."""

import asyncio
import time

from ugv import config
from ugv.geo import FRAME
from ugv.tests.test_multi_vehicle import FLEET_CFG, body, make_fleet


def test_slow_command_of_one_vehicle_does_not_block_tick(tmp_path):
    async def go():
        f, clock = make_fleet(tmp_path, FLEET_CFG[:2])
        X, Y = f.vehicles["A-ugv1"], f.vehicles["A-fire1"]
        gate = asyncio.Event()
        calls = {"X": 0, "Y": 0}

        async def slow_clear():                 # X 의 재출발 명령 응답이 오지 않는다 (8 s 넘게)
            calls["X"] += 1
            await gate.wait()

        async def fast_clear():
            calls["Y"] += 1
            Y.hold = None
        X.clear_hold, Y.clear_hold = slow_clear, fast_clear
        X.hold = {"s": 0.0, "other": "Y", "kind": "STATIC"}
        Y.hold = {"s": 0.0, "other": "X", "kind": "STATIC"}
        tm = f.traffic
        walls = []
        for _ in range(8):
            clock.advance(0.5)
            w0 = time.perf_counter()
            await tm.tick()
            walls.append(time.perf_counter() - w0)
        assert max(walls) < 1.0                       # 판단 주기가 X 응답을 기다리지 않는다
        assert calls["Y"] == 1 and Y.hold is None     # Y 는 제때 처리
        assert calls["X"] == 1 and tm._busy("A-ugv1") and tm.skipped_busy.get("A-ugv1", 0) >= 1   # X 는 중복 명령 없음
        assert tm.last_tick_sim == clock.now()
        gate.set()
        await asyncio.sleep(0)
    asyncio.run(go())


def test_command_error_is_contained(tmp_path):
    async def go():
        f, clock = make_fleet(tmp_path, FLEET_CFG[:2])
        X = f.vehicles["A-ugv1"]

        async def boom():
            raise RuntimeError("TEST_CMD_CRASH")
        X.clear_hold = boom
        X.hold = {"s": 0.0, "other": "Y", "kind": "STATIC"}
        for _ in range(4):
            clock.advance(0.5)
            await f.traffic.tick()
        assert any(e["event"] == "TRAFFIC_COMMAND_ERROR" for e in X.events)
    asyncio.run(go())


def test_stalled_traffic_supervision_stops_driving_vehicle(tmp_path):
    async def go():
        f, clock = make_fleet(tmp_path, FLEET_CFG[:2])
        A = f.vehicles["A-ugv1"]
        A.traffic_watch = f.traffic
        await A.execute(body("T1", *FRAME.to_ll(A.access.x - 900, A.access.y - 700)))
        for _ in range(20):
            clock.advance(0.5)
            for v in f.vehicles.values():
                v.driver.step(0.5)
                await v.tick()
            await f.traffic.tick()
        assert A.state == "DRIVING"
        for _ in range(int(config.TRAFFIC_STALE_S / 0.5) + 2):   # 판단 루프가 멈춘다
            clock.advance(0.5)
            A.driver.step(0.5)
            await A.tick()
        assert any(e["event"] == "TRAFFIC_SUPERVISION_STALE" for e in A.events) and A.state != "DRIVING"
    asyncio.run(go())
