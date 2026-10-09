# -*- coding: utf-8 -*-
"""UGV 시계가 환경 시계를 따라가는지 (ugv/sim_clock.py hold·release·follow_env).

실행 (저장소 루트):  python -m pytest tests/test_ugv_env_clock.py -q
"""

import time

from ugv.sim_clock import SimClock


def test_hold_until_env_moves_or_release():
    c = SimClock(time_scale=1000)
    c.hold(0.0)
    time.sleep(0.05)
    assert c.now() == 0.0 and c.held                 # 트윈 기동 중: 환경이 안 흐르면 멈춰 있다
    c.release()                                      # 첫 출발 → 그 값부터 흐른다
    time.sleep(0.05)
    assert 20 < c.now() < 500 and not c.held

    c.hold(100.0)
    r = c.follow_env(2100.0)                         # 환경이 한 스텝 나아가면 그 값으로, 다시 흐른다
    assert not c.held and r["sim_time_s"] == 2100.0
    time.sleep(0.02)
    assert 2100 < c.now() < 2600
    c.follow_env(4200.0)
    assert 4200 <= c.now() < 4400


def test_env_pause_holds_clock_and_never_goes_back():
    """트윈 시계가 총괄 LLM 을 기다리며 환경을 멈추면 UGV 시계도 '환경 + 앞섬 한도' 에서 서고, 다시 맞출 때 뒤로 가지 않는다.
    (2026-10-09 ADAIR 트윈: 우리 시계가 혼자 18분 앞서 갔다가 되돌아가며 통제가 두 번 걸렸다)"""
    c = SimClock(time_scale=1000, env_lead_max_s=200)
    c.follow_env(600.0)
    time.sleep(0.5)                                  # 벽시계로는 500초 — 환경은 멈춰 있다
    assert c.now() == 800.0                          # 600 + 200 에서 선다
    c.follow_env(660.0)                              # 환경이 다시 움직임 (우리보다 뒤)
    assert c.now() == 800.0                          # 뒤로 가지 않고, 환경이 따라올 때까지 기다린다
    c.follow_env(900.0)
    assert 900.0 <= c.now() <= 1100.0
    c.follow_env(60.0, restart=True)                 # 새 실행이면 그 시각으로 돌아간다
    assert 60.0 <= c.now() < 100.0


def test_sim_driver_moves_with_clock():
    """sim 주행은 시계가 흐른 만큼만 움직인다 — 시계가 멈추면 차도 선다."""
    import asyncio
    from ugv.drivers.sim import SimDriver

    async def run():
        c = SimClock(time_scale=100, env_lead_max_s=50)
        c.follow_env(0.0)
        d = SimDriver(start=(38.0, 128.0), speed_mps=10.0, tick_s=0.02, time_scale=100)
        d.sim_now = c.now
        await d.goto([(38.0, 128.05)], [10.0])       # 약 4.4 km
        await asyncio.sleep(1.0)                     # 시계는 50초에서 멈춤 → 최대 500 m
        moved = abs(d.position()[1] - 128.0) * 87_700
        assert 300 < moved < 560, moved
        await asyncio.sleep(0.3)
        assert abs(d.position()[1] - 128.0) * 87_700 - moved < 1    # 더 안 움직인다
        c.follow_env(300.0)                          # 환경이 다시 흐르면 따라간다
        await asyncio.sleep(0.5)
        assert abs(d.position()[1] - 128.0) * 87_700 > moved + 200
        await d.stop()
    asyncio.run(run())


def test_env_pause_follow_only_for_road_ai_demo():
    """환경 시계 멈춤 따라가기는 도로 AI 시연(UGV_AGENT=1)일 때만 기본으로 켜진다 — 평소에는 드론 mock 처럼 계속 간다."""
    import os
    import subprocess
    import sys
    code = "import ugv.config as c; print(c.ENV_LEAD_MAX_S)"
    run = lambda **env: float(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                                             env={**os.environ, "UGV_AGENT": "0", "UGV_TIME_SCALE": "100", **env}).stdout)
    assert run() == 0.0                                   # 평소 (AI 꺼짐)
    assert run(UGV_AGENT="1") == 200.0                    # 도로 AI 시연
    assert run(UGV_ENV_LEAD_MAX_S="0", UGV_AGENT="1") == 0.0   # 직접 끄기
