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
