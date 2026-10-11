# -*- coding: utf-8 -*-
"""회전 도중 교차로에 정차한 차의 출발 도로 (2026-10-11 Gazebo c23 소방차 갇힘).

교차로 495011 에서 2.5 m 떨어져 정차 — 지나온 도로 682501652 (2.6 m, 교차로까지 2.8 m 남음, 방향 차 39°) 와
다음 도로 682501875 (2.7 m, 방향 차 47°). 위치 오차 0.2 m 로 지나온 도로 끝이 출발로 잡히면 교차로 회전을 계획하지 못해
복귀·출동이 모두 거절됐다. 거의 같은 거리의 다음 도로로 출발해야 한다.
"""

import asyncio
import dataclasses
import json
from pathlib import Path

from interfaces.exec_store import ExecStore
from ugv import config
from ugv.clock import ManualClock
from ugv.fire import StaticFireSource
from ugv.geo import FRAME
from ugv.server import Fleet
from ugv.tests.test_stage3_drive import NET

STOP_LL = (38.0612694, 128.1675169)
HEADING = 173.2


def test_stopped_mid_turn_at_junction_starts_on_next_road(tmp_path):
    x, y = FRAME.to_xy(*STOP_LL)
    y += 0.2                                                     # 지나온 도로가 가장 가까워지는 위치 오차
    assert NET.snap(x, y).road_id == "682501652"
    fl = json.loads((Path(config.UGV_DIR) / "fleet_ab.json").read_text(encoding="utf-8"))
    cfg = [{**next(c for c in fl if c["resource_id"] == "A-fire1"), "driver": "sim",
            "initial": dict(zip(("lat", "lon"), FRAME.to_ll(x, y)), heading_deg=HEADING)}]
    fleet = Fleet(cfg, net=NET, fire_source=StaticFireSource([], "T", explicit=True), clock=ManualClock(),
                  store=ExecStore(tmp_path / "t.json"))
    a = fleet.vehicles["A-fire1"]
    orig = a.driver.telemetry
    a.driver.telemetry = lambda: dataclasses.replace(orig(), x=x, y=y, heading_deg=HEADING, speed_mps=0.0)
    old = a.graph.dirpos(NET.snap(x, y), HEADING)
    assert a.graph.ahead_m(old) < 5.0                              # 예전 출발: 지나온 도로 끝, 교차로 바로 앞
    st, _, err = a.here_state()
    assert err is None and st.road_id == "682501875" and a.graph.ahead_m(st) > 100.0
    acc = a.access
    r = asyncio.run(a.evaluate({"task_id": "H", "decision_id": "D", "target_node": f"RP:{acc.road_id}:{acc.s:.1f}"}))
    assert r["verdict"] == "ACCEPT", r


def test_start_road_unchanged_away_from_junction(tmp_path):
    fleet = Fleet([{**c, "driver": "sim"} for c in json.loads((Path(config.UGV_DIR) / "fleet_ab.json").read_text(encoding="utf-8"))],
                  net=NET, fire_source=StaticFireSource([], "T", explicit=True), clock=ManualClock(), store=ExecStore(tmp_path / "t.json"))
    for a in fleet.vehicles.values():
        tel = a.driver.telemetry()
        pos = NET.snap(tel.x, tel.y)
        old = a.graph.dirpos(pos, tel.heading_deg)
        st, _, _ = a.here_state()
        if a.graph.ahead_m(old) >= 15.0:
            assert (st.road_id, st.toward) == (old.road_id, old.toward)
