# -*- coding: utf-8 -*-
"""정지 명령 실패·정차 확인·정지 점유 — 실패 주입 회귀 시험 (2026-10-10 검토에서 찾은 안전 결함 4개).

1) 양보 정지 명령이 실패하면 대기를 확정하지 않고 다시 보낸다. 연속 실패면 고장(STOP_COMMAND_FAILED) + 정지 시도.
2) 비상 정지 명령이 실패하면 STOPPING 이 아니라 고장 — 정지를 계속 다시 보내고, 점유는 남은 계획 경로 전체로 보수적으로.
3) 막힘으로 임무가 실패해도 신선한 텔레메트리로 정차를 확인할 때까지 STOPPING(READY 아님), 확인되면 STOPPED_BLOCKED.
4) 정지 중인 차의 점유는 실제로 보낸 정지 경로(도로 곡선)를 따라 정지거리 + 명령 지연 거리.
"""

import asyncio
import math

from ugv.drivers import DriverError
from ugv.geo import FRAME, bearing_deg
from ugv.tests.test_multi_vehicle import FLEET_CFG, NET, body, make_fleet, run


def _drive(f, clock, A, secs):
    async def go():
        for _ in range(int(secs / 0.5)):
            clock.advance(0.5)
            for v in f.vehicles.values():
                v.driver.step(0.5)
                await v.tick()
    return go()


def _failing_follow(drv, counter):
    real = drv.follow

    async def follow(items):
        counter["n"] += 1
        if counter.get("fail", True):
            raise DriverError("TEST_INJECTED_FOLLOW_FAILURE")
        return await real(items)
    drv.follow = follow


def test_yield_hold_failure_is_retried_then_faults(tmp_path):
    async def go():
        f, clock = make_fleet(tmp_path, [FLEET_CFG[0]])
        A = f.vehicles["A-ugv1"]
        await A.execute(body("H1", *FRAME.to_ll(A.access.x - 900, A.access.y - 700)))
        await _drive(f, clock, A, 20)
        cnt = {"n": 0}
        _failing_follow(A.driver, cnt)
        s_hold = A._s_now() + 60.0
        await A.set_hold(s_hold, {"other": "X", "kind": "STATIC"})
        assert A.hold is None and cnt["n"] == 1                      # 실패하면 대기를 확정하지 않는다
        assert A.state == "DRIVING" and A.fault is None
        await A.set_hold(s_hold, {"other": "X", "kind": "STATIC"})   # 같은 대기 요청 → 다시 보낸다 (예전: 보내지 않음)
        assert cnt["n"] >= 2
        assert A.state == "FAULT" and A.fault.startswith("STOP_COMMAND_FAILED")
        assert A.command_uncertain                                    # 정지 시도도 실패 → 명령 불확실
        t = f.store.tasks["H1"]
        assert t["status"] == "FAILED" and t["progress"]["phase"] == "FAILED"
    asyncio.run(go())


def test_yield_hold_success_after_one_failure(tmp_path):
    async def go():
        f, clock = make_fleet(tmp_path, [FLEET_CFG[0]])
        A = f.vehicles["A-ugv1"]
        await A.execute(body("H2", *FRAME.to_ll(A.access.x - 900, A.access.y - 700)))
        await _drive(f, clock, A, 20)
        cnt = {"n": 0}
        _failing_follow(A.driver, cnt)
        s_hold = A._s_now() + 60.0
        await A.set_hold(s_hold, {"other": "X", "kind": "STATIC"})
        cnt["fail"] = False
        await A.set_hold(s_hold, {"other": "X", "kind": "STATIC"})
        assert A.hold is not None and abs(A.hold["s"] - s_hold) < 1e-6 and A.state == "DRIVING" and A.fault is None
    asyncio.run(go())


def test_emergency_stop_failure_is_fault_with_retry_and_wide_occupancy(tmp_path):
    async def go():
        f, clock = make_fleet(tmp_path, [FLEET_CFG[0], FLEET_CFG[2]])
        A = f.vehicles["A-ugv1"]
        await A.execute(body("E1", *FRAME.to_ll(A.access.x - 900, A.access.y - 700)))
        await _drive(f, clock, A, 25)
        assert A.driver.telemetry().speed_mps > 5
        cnt = {"n": 0}
        _failing_follow(A.driver, cnt)
        await A.traffic_emergency_stop({"vehicles": ["A-ugv1", "B-ugv1"], "kind": "TEST"})
        assert A.state == "FAULT" and A.fault.startswith("STOP_COMMAND_FAILED"), (A.state, A.fault)   # 예전: STOPPING
        assert A.command_uncertain and A.stop_path_pts is None
        # 점유: 직선만이 아니라 남은 계획 경로를 따라 (링크 단절과 같은 범위)
        pred = f.traffic._predict(A)
        far = max(p[3] for p in pred.samples)
        assert far > A.profile.stop_distance(A.driver.telemetry().speed_mps) + 20
        # 정지 재시도 (STOP_RETRY_S 뒤), 성공하면 불확실 해제·고장 상태 유지
        n0 = cnt["n"]
        cnt["fail"] = False
        clock.advance(2.5)
        await A.tick()
        assert cnt["n"] > n0 and not A.command_uncertain and A.state == "FAULT"
        assert any(e["event"] == "STOP_RETRY" and e["ok"] for e in A.events)
    asyncio.run(go())


def test_blocked_failure_stays_stopping_until_stopped(tmp_path):
    """출발 도로 앞 고장 차(우회 없음) → 임무 FAILED BLOCKED_BY_VEHICLE. 아직 움직이면 STOPPING·READY 아님, 서면 IDLE·STOPPED_BLOCKED."""
    async def go():
        A0 = {**FLEET_CFG[0], "resource_id": "X-ugv"}
        probe, _ = make_fleet(tmp_path / "p", [A0])
        X0 = probe.vehicles["X-ugv"]
        acc = X0.access
        p2, q2 = NET.at(acc.road_id, acc.s + 60.0), NET.at(acc.road_id, acc.s + 61.0)
        cfg = [A0, {**FLEET_CFG[2], "resource_id": "Y-ugv", "initial": {"lat": FRAME.to_ll(p2.x, p2.y)[0],
               "lon": FRAME.to_ll(p2.x, p2.y)[1], "heading_deg": bearing_deg(q2.x - p2.x, q2.y - p2.y)}}]
        f, clock = make_fleet(tmp_path / "a", cfg)
        X, Y = f.vehicles["X-ugv"], f.vehicles["Y-ugv"]
        Y._fail("VEHICLE_FAULT", "시험 주입")
        # 출발 전 막힘 거절(ROAD_BLOCKED)을 건너뛰어 '계획 뒤 앞차가 선' 주행 중 막힘을 본다
        X._check_start_road_blocker = lambda plan, start, home: plan
        await X.execute(body("B1", *FRAME.to_ll(acc.x - 900, acc.y - 700)))
        seen_moving_after_fail = False
        for _ in range(240):
            clock.advance(0.5)
            for v in f.vehicles.values():
                v.driver.step(0.5)
                await v.tick()
            await f.traffic.tick()
            t = f.store.tasks["B1"]
            if t["status"] == "FAILED" and X.driver.telemetry().speed_mps > 0.3:
                seen_moving_after_fail = True
                assert X.state == "STOPPING" and X.resource_state() != "READY" and t["physical_state"] == "STOPPING_BLOCKED"
            if t["status"] == "FAILED" and X.state == "IDLE":
                break
        t = f.store.tasks["B1"]
        assert t["status"] == "FAILED" and t["error"].startswith("BLOCKED_BY_VEHICLE")
        assert X.state == "IDLE" and X.driver.telemetry().speed_mps < 0.2 and t["physical_state"] == "STOPPED_BLOCKED"
        assert seen_moving_after_fail                                  # 실패 보고 때 아직 움직이던 경우를 실제로 거쳤다
    asyncio.run(go())


def test_stopping_occupancy_follows_sent_stop_path_on_curve(tmp_path):
    """곡선 경로를 달리던 차가 정지(_safe_stop) — 점유 표본은 보낸 정지 경로(곡선) 위에 있고 직선 예측과 다르다."""
    async def go():
        f, clock = make_fleet(tmp_path, [FLEET_CFG[0]])
        A = f.vehicles["A-ugv1"]
        await A.execute(body("C1", *FRAME.to_ll(A.access.x - 900, A.access.y - 700)))
        sp = A.speed
        best = None
        for _ in range(400):                                 # 앞쪽 정지거리 안에 뚜렷한 곡선이 있는 순간을 찾는다
            clock.advance(0.5)
            A.driver.step(0.5)
            await A.tick()
            tel = A.driver.telemetry()
            if tel.speed_mps < 5:
                continue
            d = A.profile.stop_distance(tel.speed_mps)
            path = A._path_between(A._s_now() + d)
            hd = math.radians(tel.heading_deg)
            dev = max(abs((q[0] - tel.x) * math.cos(hd) - (q[1] - tel.y) * math.sin(hd)) for q in path)
            if dev > 3.0:
                best = dev
                break
        assert best is not None, "곡선 앞 순간 없음"
        await A._safe_stop()
        assert A.state == "STOPPING" and A.stop_path_pts
        pred = f.traffic._predict(A)
        stop = A.stop_path_pts

        def dist_to(path, x, y):
            m = math.inf
            for (ax, ay), (bx, by) in zip(path, path[1:]):
                dx, dy = bx - ax, by - ay
                L2 = dx * dx + dy * dy
                t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
                m = min(m, math.hypot(x - ax - t * dx, y - ay - t * dy))
            return m
        rac = A.profile.rear_axle_from_center_m                 # 표본은 차체 중심 (정지 경로는 뒤축 경로)
        assert all(dist_to(stop, x - rac * hx, y - rac * hy) < 0.5 for x, y, _t, _s, hx, hy in pred.samples)
        tel = A.driver.telemetry()
        hd = math.radians(tel.heading_deg)
        lateral = max(abs((x - tel.x) * math.cos(hd) - (y - tel.y) * math.sin(hd)) for x, y, *_ in pred.samples)
        assert lateral > 1.0                                  # 직선 예측(옆 0 m)이 아니다
    asyncio.run(go())


def _center(v):
    t = v.driver.telemetry()
    if getattr(v.driver, "position_ref", "rear_axle") == "center":
        return t.x, t.y
    yaw = math.radians(90.0 - t.heading_deg)
    rac = v.profile.rear_axle_from_center_m
    # sim 드라이버 위치 = 뒤축 → 차체 중심은 진행 방향으로 뒤축~중심 거리만큼 앞
    return t.x + rac * math.cos(yaw), t.y + rac * math.sin(yaw)


def _as_px4_center(v):
    """sim 드라이버 텔레메트리를 PX4 처럼 차체 중심(GPS) 위치로 낸다 (Gazebo 에서 드러난 기준점 혼용 재현)."""
    import dataclasses
    drv, rac = v.driver, v.profile.rear_axle_from_center_m
    real = drv.telemetry

    def tel():
        t = real()
        yaw = math.radians(90.0 - t.heading_deg)
        return dataclasses.replace(t, x=t.x + rac * math.cos(yaw), y=t.y + rac * math.sin(yaw))
    drv.telemetry, drv.position_ref = tel, "center"


def _stopped_gap(tmp_path, ahead_m):
    async def go():
        A0 = {**FLEET_CFG[0], "resource_id": "X-ugv"}
        probe, _ = make_fleet(tmp_path / f"p{ahead_m}", [A0])
        acc = probe.vehicles["X-ugv"].access
        p2, q2 = NET.at(acc.road_id, acc.s + ahead_m), NET.at(acc.road_id, acc.s + ahead_m + 1.0)
        cfg = [A0, {**FLEET_CFG[3], "resource_id": "Y-fire", "initial": {"lat": FRAME.to_ll(p2.x, p2.y)[0],
               "lon": FRAME.to_ll(p2.x, p2.y)[1], "heading_deg": bearing_deg(q2.x - p2.x, q2.y - p2.y)}}]
        f, clock = make_fleet(tmp_path / f"a{ahead_m}", cfg)
        X, Y = f.vehicles["X-ugv"], f.vehicles["Y-fire"]
        for v in (X, Y):
            _as_px4_center(v)
        Y._fail("VEHICLE_FAULT", "시험 주입")
        X._check_start_road_blocker = lambda plan, start, home: plan      # 주행 중 막힘 (출발 전 거절 건너뜀)
        await X.execute(body("G1", *FRAME.to_ll(acc.x - 900, acc.y - 700)))
        vmax = 0.0
        for _ in range(400):
            clock.advance(0.5)
            for v in f.vehicles.values():
                v.driver.step(0.5)
                await v.tick()
            await f.traffic.tick()
            vmax = max(vmax, X.driver.telemetry().speed_mps)
            if f.store.tasks["G1"]["status"] == "FAILED" and X.state == "IDLE":
                break
        (xa, ya), (xb, yb) = _center(X), _center(Y)
        return math.hypot(xa - xb, ya - yb) - (X.profile.body_length_m + Y.profile.body_length_m) / 2, vmax, X.state
    return asyncio.run(go())


def test_stopped_vehicle_gap_meets_4m_center_basis(tmp_path):
    """서 있는 차 앞에서 선 간격 = 차체 중심 거리 − 차체 길이 절반 합 ≥ TRAFFIC_GAP_M (4 m). 같은 사례(출발 도로 60 m 앞)와
    더 빠르게 접근하는 사례(250 m 앞). 텔레메트리는 PX4 처럼 차체 중심. 예전에는 상대 위치(중심)와 내 길(뒤축 경로)을 섞어 재고 대기 지점을 충돌 표본 − 3 m 로
    잡아 Gazebo 에서 2.62~2.88 m 였다."""
    from ugv.traffic import TRAFFIC_GAP_M
    for ahead in (60.0, 250.0):
        gap, vmax, st = _stopped_gap(tmp_path, ahead)
        assert st == "IDLE", st
        assert gap >= TRAFFIC_GAP_M - 0.05, (ahead, gap, vmax)


def test_closer_hold_point_is_resent(tmp_path):
    """대기 지점이 0.3 m 넘게 가까워지면 다시 보낸다 (FOLLOW → STATIC 로 바뀌어 더 앞에서 서야 할 때). 예전: 1 m 까지 무시."""
    async def go():
        f, clock = make_fleet(tmp_path, [FLEET_CFG[0]])
        A = f.vehicles["A-ugv1"]
        await A.execute(body("R1", *FRAME.to_ll(A.access.x - 900, A.access.y - 700)))
        await _drive(f, clock, A, 15)
        cnt = {"n": 0, "fail": False}
        _failing_follow(A.driver, cnt)
        s1 = A._s_now() + 80.0
        await A.set_hold(s1, {"other": "Y", "kind": "FOLLOW"})
        await A.set_hold(s1 - 0.9, {"other": "Y", "kind": "STATIC"})
        assert cnt["n"] == 2 and abs(A.hold["s"] - (s1 - 0.9)) < 1e-6
        await A.set_hold(s1 - 1.0, {"other": "Y", "kind": "STATIC"})      # 0.1 m 차이는 그대로
        assert cnt["n"] == 2
    asyncio.run(go())


def test_stop_command_without_response_is_treated_as_failure(tmp_path, monkeypatch):
    """응답이 오지 않는 정지·양보 명령: 시간 제한 뒤 '전달 여부 불명' 실패로 — 대기를 확정하지 않는다."""
    import ugv.vehicle as V
    monkeypatch.setattr(V, "STOP_CMD_TIMEOUT_S", 0.2)

    async def go():
        f, clock = make_fleet(tmp_path, [FLEET_CFG[0]])
        A = f.vehicles["A-ugv1"]
        await A.execute(body("T1", *FRAME.to_ll(A.access.x - 900, A.access.y - 700)))
        await _drive(f, clock, A, 15)

        async def hang(items):
            await asyncio.sleep(5)
        A.driver.follow = hang
        await A.set_hold(A._s_now() + 60.0, {"other": "Y", "kind": "STATIC"})
        assert A.hold is None
        e = [x for x in A.events if x["event"] == "YIELD_FAILED"][-1]
        assert "STOP_COMMAND_TIMEOUT" in e["detail"]
    asyncio.run(go())


def test_telemetry_loss_with_failed_stop_keeps_link_loss_occupancy(tmp_path):
    """위치 수신 중단 + 정지 명령 실패: 고장(TELEMETRY_LOST), 명령 불확실, 점유는 마지막 위치부터 계획 경로를 따라 링크 단절 범위."""
    import dataclasses
    import time as _t
    from ugv.traffic import link_loss_reach

    async def go():
        f, clock = make_fleet(tmp_path, [FLEET_CFG[0], FLEET_CFG[2]])
        A = f.vehicles["A-ugv1"]
        await A.execute(body("L1", *FRAME.to_ll(A.access.x - 900, A.access.y - 700)))
        await _drive(f, clock, A, 20)
        real = A.driver.telemetry
        A.driver.telemetry = lambda: dataclasses.replace(real(), updated_mono=_t.monotonic() - 60)   # 60 s 낡음
        cnt = {"n": 0}
        _failing_follow(A.driver, cnt)
        A.driver.stop = lambda: (_ for _ in ()).throw(DriverError("TEST_STOP_FAIL"))
        await A.tick()
        assert A.state == "FAULT" and A.fault.startswith("TELEMETRY_LOST") and A.command_uncertain
        pred = f.traffic._predict(A)
        sp = A.speed
        i0 = max(0, min(A._near_i, len(sp.pts) - 1))
        reach = link_loss_reach(sp, i0, real().speed_mps)
        assert max(p[3] for p in pred.samples) >= min(reach, sp.cum[-1] - sp.cum[i0]) - 10.0
    asyncio.run(go())


def test_arrival_ready_only_after_standstill(tmp_path):
    """미션이 끝나도 0.2 m/s 이상으로 움직이면 도착·READY 가 아니다 (Gazebo: 0.3~0.5 m/s 로 굴러가는데 READY 였다)."""
    import dataclasses

    async def go():
        f, clock = make_fleet(tmp_path, [FLEET_CFG[0]])
        A = f.vehicles["A-ugv1"]
        drv = A.driver
        real = drv.telemetry
        creep = {"on": False}

        def tel():
            t = real()
            return dataclasses.replace(t, speed_mps=0.35) if creep["on"] else t
        drv.telemetry = tel
        tgt = FRAME.to_ll(A.access.x - 300, A.access.y - 250)
        await A.execute(body("AR1", *tgt))
        seen = False
        for _ in range(1200):
            clock.advance(0.5)
            drv.step(0.5)
            if drv.progress().finished and not seen:
                creep["on"], seen = True, True           # 미션 끝난 순간부터 잠깐 굴러감
            await A.tick()
            if seen and creep["on"]:
                assert A.state != "IDLE" and A.resource_state() != "READY", "굴러가는데 도착·READY"
                creep["n"] = creep.get("n", 0) + 1
                if creep["n"] >= 6:
                    creep["on"] = False                   # 3 s 뒤 멈춤
            if seen and not creep["on"] and A.state == "IDLE":
                break
        assert seen and A.state == "IDLE" and f.store.tasks["AR1"]["status"] == "COMPLETED"
    asyncio.run(go())
