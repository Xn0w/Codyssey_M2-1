# -*- coding: utf-8 -*-
# 작성: AI 코딩 도구(Claude Code)를 사용해 작성·검토한 코드다.
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


def test_env_lead_cap_stops_when_env_stops():
    c = SimClock(time_scale=1000, env_lead_max_s=200)
    c.follow_env(116100.0)                           # 시나리오 끝: 환경이 더 나아가지 않는다
    time.sleep(0.5)                                  # 벽시계 × 1000 이면 500 초 넘게 갈 시간
    assert c.now() == 116300.0                       # 마지막 환경 시각 + 200 에서 멈춘다
    time.sleep(0.05)
    assert c.now() == 116300.0


def test_env_lead_cap_follows_env_again_and_resets():
    c = SimClock(time_scale=1000, env_lead_max_s=200)
    c.follow_env(1000.0)
    time.sleep(0.3)
    assert c.now() == 1200.0
    c.follow_env(1060.0)                             # 환경이 다시 나아가면 그 값에서 다시 흐른다
    assert 1060.0 <= c.now() <= 1260.0
    c.reset(0.0)                                     # 새 실행: 한도 기준도 지운다 (환경 없이 단독이면 한도 없음)
    time.sleep(0.3)
    assert c.now() > 250


def test_no_cap_without_env_or_when_off():
    c = SimClock(time_scale=1000, env_lead_max_s=200)
    time.sleep(0.3)
    assert c.now() > 250                             # 환경을 한 번도 안 받았으면 예전처럼 간다
    c = SimClock(time_scale=1000)
    c.follow_env(1000.0)
    time.sleep(0.3)
    assert c.now() > 1250                            # 한도를 끄면(None) 예전처럼 간다
