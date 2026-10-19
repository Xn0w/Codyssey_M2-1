# -*- coding: utf-8 -*-
"""양보 대기 해제 재출발 ↔ '주행 중 시동 꺼짐' 감시 경합 (2026-10-19 Gazebo 4대 logs/ugv/stage6/multi/rgf_02 A-ugv1).

대기 지점에 다 서면 PX4 드라이버 정차 유지(_park_watch)가 시동을 끈다 (대기 중이라 감시는 시동 판정을 건너뜀).
대기가 풀리면 clear_hold → follow. PX4 follow 는 진행 상태를 새 미션(미완료)으로 먼저 바꾸고 업로드·시동에 ~1 s 걸린다
→ 그 사이 감시 tick 이 잠금 밖에서 '시동 꺼짐·출발 5 s 지남·정차 유지 아님' 을 계산해 잠금을 기다렸다가, 재출발이 끝난 뒤
다시 확인하지 않고 VEHICLE_FAULT 로 고장 처리했다 (한 번도 안 움직인 차).
수정: ① 잠금 안에서 다시 확인 ② 대기(hold)는 재출발 명령이 끝난 뒤에 지운다.
"""
import asyncio
import dataclasses

from ugv.drivers.base import Progress
from ugv.geo import FRAME
from ugv.tests.test_multi_vehicle import body, make_fleet


async def _parked_at_yield(tmp_path):
    """A-ugv1 을 20 s 달린 뒤 30 m 앞 대기 지점에 세우고, PX4 처럼 정차 유지로 시동을 끈 상태로 5 s 둔다."""
    f, clock = make_fleet(tmp_path)
    clock.advance(100.0)
    A = f.vehicles["A-ugv1"]
    assert (await A.execute(body("D1", *FRAME.to_ll(A.access.x - 900, A.access.y - 700))))["status"] == "STARTED"
    for _ in range(40):
        clock.advance(0.5)
        A.driver.step(0.5)
        await A.tick()
    drv = A.driver
    drv.kind = "px4"
    drv.parked_seq = None
    real_tel = drv.telemetry
    st = {"armed": True}
    drv.telemetry = lambda: dataclasses.replace(real_tel(), armed=st["armed"])
    await A.set_hold(A._s_now() + 30.0, {"other": "A-fire1", "kind": "CROSS", "why": "CROSS_PRIORITY"})
    assert A.hold is not None and A.state == "DRIVING"
    for _ in range(200):
        clock.advance(0.5)
        drv.step(0.5)
        await A.tick()
        if drv.progress().finished and drv.telemetry().speed_mps < 0.2:
            break
    assert drv.progress().finished and A.hold is not None and A.fault is None
    clock.advance(1.0)                                     # 정차 유지 (px4.py _park_watch): 정지 1 s 뒤 시동 끔
    drv.step(1.0)
    drv.parked_seq = drv.progress().mission_seq
    st["armed"] = False
    for _ in range(10):                                    # 시동 꺼진 채 대기 5 s — 고장 아님
        clock.advance(0.5)
        drv.step(0.5)
        await A.tick()
    assert A.fault is None and A.state == "DRIVING", A.fault
    return f, clock, A, st


def _px4_like_follow(A, st, gate: asyncio.Event, log: list):
    """PX4 드라이버 follow 흉내 (px4.py follow): 진행 상태를 새 미션(미완료)으로 먼저 바꾸고, 업로드(gate 를 기다림) 뒤 시동."""
    drv = A.driver
    real_follow = drv.follow

    async def follow(items):
        seq0 = drv._prog.mission_seq
        drv._prog = Progress(0, len(items), False, seq0 + 1)
        log.append("follow_begin")
        await gate.wait()                                  # upload_mission
        st["armed"] = True                                 # _ensure_armed
        drv._prog = Progress(0, 0, False, seq0)
        log.append("armed")
        return await real_follow(items)
    return follow


def test_resume_after_parked_yield_upload_window_is_not_disarm_fault(tmp_path):
    """감시 tick 이 재출발 업로드 창(시동 꺼짐·진행 미완료) 안에 돌아도 고장이 아니고 미션을 다시 달린다."""
    async def go():
        f, clock, A, st = await _parked_at_yield(tmp_path)
        gate, log = asyncio.Event(), []
        A.driver.follow = _px4_like_follow(A, st, gate, log)
        seq_before = A.seq
        resume = asyncio.create_task(A.clear_hold())
        for _ in range(20):
            await asyncio.sleep(0)
            if log:
                break
        assert log == ["follow_begin"]
        clock.advance(0.5)
        A.driver.step(0.5)
        tick = asyncio.create_task(A.tick())               # 업로드 창 안의 감시 주기
        for _ in range(20):
            await asyncio.sleep(0)
        gate.set()                                         # 업로드 끝 → 시동 → 미션 시작
        await asyncio.gather(resume, tick)
        assert A.fault is None and A.state == "DRIVING", A.fault
        assert A.hold is None and A.seq != seq_before
        evs = [e["event"] for e in f.store.events if e.get("resource_id") == "A-ugv1"] \
            if hasattr(f.store, "events") else None
        for _ in range(10):                                # 다시 달린다
            clock.advance(0.5)
            A.driver.step(0.5)
            await A.tick()
        assert A.fault is None and A.state == "DRIVING", A.fault
        assert A.driver.telemetry().speed_mps > 0.5
        assert f.store.tasks["D1"]["status"] == "IN_PROGRESS"
        assert evs is None or "FAULT" not in evs
    asyncio.run(go())


def test_disarm_recheck_under_lock_sees_resume(tmp_path):
    """① 잠금 안 재확인: 감시가 잠금 밖에서 '주행 중 시동 꺼짐' 을 계산하고 잠금을 기다리는 동안 재출발이 시동을 걸고
    출발 시각을 바꾸면 고장 처리하지 않는다 (대기 hold 와 상관없이)."""
    async def go():
        f, clock, A, st = await _parked_at_yield(tmp_path)
        A.hold = None                                      # 대기 보호 없이 잠금 경합만 본다
        A.driver._prog = Progress(0, 5, False, A.driver._prog.mission_seq + 1)   # 정차 유지 보호 풀림 (새 미션 진행)
        A.seq = A.driver._prog.mission_seq
        async with A.lock:
            tick = asyncio.create_task(A.tick())
            for _ in range(20):
                await asyncio.sleep(0)
            assert not tick.done()                          # 판정을 계산하고 잠금을 기다리는 중
            st["armed"] = True                              # 그 사이 재출발: 시동·출발 시각
            A._drive_started_sim = clock.now()
        await tick
        assert A.fault is None and A.state == "DRIVING", A.fault
    asyncio.run(go())


def test_real_disarm_after_resume_still_detected(tmp_path):
    """수정 뒤에도 재출발한 차가 주행 중 시동이 꺼지면 (유예 5 s 뒤) 다음 감시 주기에 VEHICLE_FAULT·정지 미션."""
    async def go():
        f, clock, A, st = await _parked_at_yield(tmp_path)
        gate, log = asyncio.Event(), []
        A.driver.follow = _px4_like_follow(A, st, gate, log)
        gate.set()
        await A.clear_hold()
        assert A.hold is None and A.fault is None
        for _ in range(14):                                 # 7 s 주행 (재출발 유예 5 s 를 지난다)
            clock.advance(0.5)
            A.driver.step(0.5)
            await A.tick()
        assert A.fault is None and A.state == "DRIVING", A.fault
        st["armed"] = False                                 # 주행 중 진짜 시동 꺼짐
        seq_before = A.seq
        clock.advance(0.5)
        A.driver.step(0.5)
        await A.tick()
        assert A.state == "FAULT" and A.fault.startswith("VEHICLE_FAULT"), A.fault
        assert A.seq != seq_before                          # 정지 미션으로 바꿈
    asyncio.run(go())


def test_resume_failure_clears_hold(tmp_path):
    """재출발 명령 실패: 대기를 지우고 RESUME_FAILED 고장·정지 (예전과 같음)."""
    from ugv.drivers.base import DriverError

    async def go():
        f, clock, A, st = await _parked_at_yield(tmp_path)

        async def bad_follow(items):
            raise DriverError("MISSION_START_FAILED: test")
        A.driver.follow = bad_follow
        await A.clear_hold()
        assert A.hold is None and A.state == "FAULT" and A.fault.startswith("RESUME_FAILED"), A.fault
    asyncio.run(go())
