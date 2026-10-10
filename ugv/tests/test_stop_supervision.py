# -*- coding: utf-8 -*-
"""정지 감독 — 정지 명령 뒤 실제 속도·이동 거리·시간을 텔레메트리로 확인하고, 서지 않으면 구동 차단.

재현 (2026-10-11 Gazebo 지속 운용): 고장 주입 → 정지 경로 64 m → 미션 끝 2.9 m/s 로 PX4 대기(HOLD)에서 직진, FAULT 상태로 2.6 km.
sim 드라이버 시험 훅: runaway_mps (미션 끝에서 서지 않고 직진), hide_finish (완료 신호 누락), fail_cut (차단 명령 실패).
"""

import asyncio

from ugv import vehicle as VM
from ugv.geo import FRAME
from ugv.tests.test_multi_vehicle import FLEET_CFG, body, make_fleet


async def _steps(f, clock, secs, every=None):
    for _ in range(int(secs / 0.5)):
        clock.advance(0.5)
        for v in f.vehicles.values():
            v.driver.step(0.5)
            await v.tick()
        if every:
            every()


async def _fault_at_speed(tmp_path, **hooks):
    f, clock = make_fleet(tmp_path, [FLEET_CFG[0]])
    A = f.vehicles["A-ugv1"]
    await A.execute(body("S1", *FRAME.to_ll(A.access.x - 900, A.access.y - 700)))
    await _steps(f, clock, 25)
    assert A.driver.telemetry().speed_mps > 5
    for k, val in hooks.items():
        setattr(A.driver, k, val)
    async with A.lock:                         # 서버 /_test/fault 와 같은 순서
        A._fail("VEHICLE_FAULT", "시험 주입")
        await A._safe_stop()
        A.state = "FAULT"
    return f, clock, A


def _ev(A, name):
    return [e for e in A.events if e["event"] == name]


def test_runaway_after_stop_mission_is_cut_and_confirmed(tmp_path):
    async def go():
        f, clock, A = await _fault_at_speed(tmp_path, runaway_mps=2.9)
        allow = A._stop_sup["allow_m"]
        states = []
        await _steps(f, clock, 60, lambda: states.append(A.resource_state()))
        assert _ev(A, "STOP_NOT_CONFIRMED") and _ev(A, "STOP_CUT_DRIVE")[0]["ok"]
        res = _ev(A, "STOP_CONFIRMED")[-1]
        assert res["cut_drive"] and res["travel_m"] <= allow + 2.9 * 0.5 + 0.5 + 2.9 ** 2 / (2 * A.driver.decel)
        assert A.driver.telemetry().speed_mps == 0.0 and A.state == "FAULT"
        assert "READY" not in states
    asyncio.run(go())


def test_missing_finish_signal_does_not_disable_supervision(tmp_path):
    async def go():
        f, clock, A = await _fault_at_speed(tmp_path, runaway_mps=2.9, hide_finish=True)
        await _steps(f, clock, 60)
        assert _ev(A, "STOP_CUT_DRIVE") and _ev(A, "STOP_CONFIRMED")
        assert A.driver.telemetry().speed_mps == 0.0
    asyncio.run(go())


def test_cut_failure_is_retried_and_release_refused_until_stopped(tmp_path):
    async def go():
        f, clock, A = await _fault_at_speed(tmp_path, runaway_mps=2.9, fail_cut="TEST_CUT_FAILURE")
        await _steps(f, clock, 40)
        cuts = _ev(A, "STOP_CUT_DRIVE")
        assert len(cuts) >= 3 and not any(c["ok"] for c in cuts)
        assert A.stop_cut_active and A.resource_state() == "UNAVAILABLE" and not _ev(A, "STOP_CONFIRMED")
        r = await A.stop("운영자")
        assert r["released_fault"] is None and r["release_pending"]           # 서지 않았으니 해제 안 함
        assert A.driver.telemetry().armed is True and A.driver.cut is False  # 정지 미션을 다시 보내 시동을 걸지 않았다
        A.driver.fail_cut = None
        await _steps(f, clock, 10)
        assert _ev(A, "STOP_CONFIRMED") and A.driver.telemetry().speed_mps == 0.0
        r = await A.stop("운영자")
        assert r["released_fault"] and A.resource_state() == "RUNNING"     # 해제 뒤 제자리 정지도 정차 확인까지 READY 아님
        await _steps(f, clock, 3)
        assert A.resource_state() == "READY"
    asyncio.run(go())


def test_normal_stop_is_confirmed_without_cut(tmp_path):
    async def go():
        f, clock, A = await _fault_at_speed(tmp_path)
        await _steps(f, clock, 30)
        res = _ev(A, "STOP_CONFIRMED")[-1]
        assert not res["cut_drive"] and res["travel_m"] <= res["allow_m"] and not _ev(A, "STOP_CUT_DRIVE")
    asyncio.run(go())


def test_restart_with_runaway_is_stopped_and_cut(tmp_path):
    async def go():
        f, clock = make_fleet(tmp_path, [FLEET_CFG[0]])
        A = f.vehicles["A-ugv1"]
        await A.execute(body("R1", *FRAME.to_ll(A.access.x - 900, A.access.y - 700)))
        await _steps(f, clock, 25)
        A.driver.runaway_mps = 2.9
        f.store.tasks["R1"]["status"] = "FAILED"            # 재시작 흉내: 임무 기록·상태만 잃는다
        A.task_key, A.state, A.speed, A.plan = None, "IDLE", None, None
        states = []
        await _steps(f, clock, 80, lambda: states.append(A.resource_state()))
        assert _ev(A, "UNSUPERVISED_MOTION_STOP") and _ev(A, "STOP_CUT_DRIVE") and _ev(A, "STOP_CONFIRMED")
        assert A.driver.telemetry().speed_mps == 0.0
        assert all(s != "READY" for s in states[:states.index("UNAVAILABLE") + 1])
    asyncio.run(go())


def test_fault_vehicle_moving_again_after_confirmed_stop_is_stopped(tmp_path):
    async def go():
        f, clock, A = await _fault_at_speed(tmp_path)
        await _steps(f, clock, 30)
        assert _ev(A, "STOP_CONFIRMED") and A._stop_sup is None
        x, y = A.driver.x, A.driver.y                      # 차가 스스로 다시 움직인다 (남은 미션 재개 흉내)
        await A.driver.follow([(x - 200, y, 6.0)])
        await _steps(f, clock, 60)
        ums = _ev(A, "UNSUPERVISED_MOTION_STOP")
        assert ums and ums[0]["state"] == "FAULT" and A.state == "FAULT"
        assert len(_ev(A, "STOP_CONFIRMED")) >= 2 and A.driver.telemetry().speed_mps < 0.2
    asyncio.run(go())


def test_traffic_treats_cut_vehicle_as_uncertain(tmp_path):
    async def go():
        f, clock, A = await _fault_at_speed(tmp_path, runaway_mps=2.9, fail_cut="X")
        await _steps(f, clock, 20)
        assert A.stop_cut_active and A.stop_path_pts is None
    asyncio.run(go())


def test_speed_alternating_around_threshold_is_cut_by_time(tmp_path):
    """미션 끝 뒤 0.29↔0.31 m/s 로 기어가도 정지 감독이 시간 상한으로 차단한다 (끝없이 미뤄지지 않음)."""
    async def go():
        f, clock, A = await _fault_at_speed(tmp_path)
        await _steps(f, clock, 30)
        assert _ev(A, "STOP_CONFIRMED")
        await A._safe_stop()                                 # 운영자 정지 요청 → 감독 시작
        A.state = "FAULT"
        # 그 뒤 차가 미션 끝 대기에서 0.29↔0.31 m/s 로 기어간다 (감독 없는 움직임 문턱 0.5 m/s 미만)
        A.driver.runaway_mps = 0.31
        A.driver._prog = A.driver._prog.__class__(1, 1, True, A.driver._prog.mission_seq)
        A.driver.path = [(A.driver.x, A.driver.y, 1.0)]
        k = [0]

        def alt():
            k[0] += 1
            A.driver.runaway_mps = 0.31 if k[0] % 2 else 0.29
        await _steps(f, clock, 30, alt)
        assert _ev(A, "STOP_CUT_DRIVE") and "TIME" in _ev(A, "STOP_NOT_CONFIRMED")[0]["why"]
    asyncio.run(go())


def test_stop_retries_do_not_reset_supervision(tmp_path):
    async def go():
        f, clock, A = await _fault_at_speed(tmp_path, runaway_mps=2.9)
        t0, allow = A._stop_sup["t0"], A._stop_sup["allow_m"]
        for _ in range(3):
            await _steps(f, clock, 1)
            if A._stop_sup and not A.stop_cut_active:
                await A._safe_stop()                         # 재시도·반복 /stop
                A.state = "FAULT"
        s = A._stop_sup
        assert s is None or (s["t0"] == t0 and s["allow_m"] == allow)
        await _steps(f, clock, 40)
        assert _ev(A, "STOP_CUT_DRIVE") and _ev(A, "STOP_CONFIRMED")
    asyncio.run(go())


def test_stop_path_never_plans_faster_than_current_speed(tmp_path):
    """정지 경로 미션 속도는 지금 속도 이하 (2026-10-11 Gazebo: 정지 거리 여유 때문에 시작 구간에서 가속 → 감속 안 함으로 차단·고장)."""
    async def go():
        f, clock = make_fleet(tmp_path, [FLEET_CFG[0]])
        A = f.vehicles["A-ugv1"]
        await A.execute(body("P1", *FRAME.to_ll(A.access.x - 900, A.access.y - 700)))
        await _steps(f, clock, 25)
        v0 = A.driver.telemetry().speed_mps
        assert v0 > 5
        await A.abort("P1")
        assert max(it[2] for it in A.driver.path) <= v0 + 1e-6
        await _steps(f, clock, 30)
        res = _ev(A, "STOP_CONFIRMED")[-1]
        assert not res["cut_drive"] and not res["exceeded_allow"] and A.fault is None
    asyncio.run(go())
