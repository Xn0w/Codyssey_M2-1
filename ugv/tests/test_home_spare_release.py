# -*- coding: utf-8 -*-
"""2026-10-11 Gazebo c23 지속 운용 B-fire1 거점 옆 갇힘 (원인 검증: Fable 서브에이전트).

1) 먼 목표 선택: 목표 1000 m 안에 갈 수 있는 지점이 없을 때 '전체 중 가장 빠른 후보(출발점 바로 앞)' 가 기준이 돼
   1.9 km 떨어진 목표가 12 m 앞 지점으로 풀렸다 → 목표에 가장 가까운 후보를 기준으로.
2) 복귀: 같은 거점 다른 차(B-ugv1)의 대기 도로 683400513 을 무조건 피했는데, 회전 모형상 그 도로가 거점 주변과 도로망을 잇는
   유일한 연결로라 복귀가 계속 거절됐다 → 피해서 경로가 없으면 (그 차가 지금 그 도로에 없을 때) 넣어 다시 계획하고 보고.
"""

import asyncio
import dataclasses
import json
import math
from pathlib import Path

from interfaces.exec_store import ExecStore
from ugv import approach as AP
from ugv import config
from ugv.clock import ManualClock
from ugv.fire import EMPTY, StaticFireSource
from ugv.geo import FRAME
from ugv.profiles import get as get_profile
from ugv.server import Fleet
from ugv.tests.test_stage3_drive import NET

POSES = {  # c23 서버 /ugv 상태 (Fable 재현과 같은 값)
    "A-ugv1": (38.0616978, 128.168131, 225.9),
    "A-fire1": (38.0402600, 128.2121567, 132.6),
    "B-ugv1": (37.9576932, 128.3184182, 184.3),
    "B-fire1": (37.9590862, 128.3186418, 24.8),
}


def test_far_target_does_not_collapse_to_point_ahead():
    g = NET.graph_for(get_profile("adair_firetruck"))
    x, y = FRAME.to_xy(37.9589857, 128.3185811)
    start = g.dirpos(NET.snap(x, y), 26.1)                       # SH5 도착 자세 (683400570 s 35.3, 495692 쪽)
    acc = NET.at("683400570", 35.0)
    tgt = (37.951004, 128.337462)                                # SK8 목표 (도로에서 먼 곳)
    plan = AP.plan_approach(NET, EMPTY, start, *tgt, v0=0.0, access=acc, graph=g, avoid_roads={"683400732": "B-ugv1"})
    assert plan.status == "OK"
    tx, ty = FRAME.to_xy(*tgt)
    assert math.hypot(plan.dest.x - tx, plan.dest.y - ty) < 1800.0          # 예전: 1881 m (12 m 앞 지점)
    assert not (plan.dest.road_id == "683400570" and abs(plan.dest.s - start.pos.s) < 20.0)


def test_home_releases_peer_spare_road_when_no_other_route(tmp_path):
    fl = json.loads((Path(config.UGV_DIR) / "fleet_ab.json").read_text(encoding="utf-8"))
    cfg = [{**c, "driver": "sim", "initial": dict(zip(("lat", "lon", "heading_deg"), POSES[c["resource_id"]]))} for c in fl]
    f = Fleet(cfg, net=NET, fire_source=StaticFireSource([], "T", explicit=True), clock=ManualClock(),
              store=ExecStore(tmp_path / "t.json"))
    for rid, v in f.vehicles.items():
        la, lo, hd = POSES[rid]
        X, Y = FRAME.to_xy(la, lo)
        v.driver.telemetry = (lambda o, X, Y, hd: (lambda: dataclasses.replace(o(), x=X, y=Y, heading_deg=hd, speed_mps=0.0)))(
            v.driver.telemetry, X, Y, hd)
    B = f.vehicles["B-fire1"]
    assert "683400513" in B.occupied_roads(home=True)                      # B-ugv1 대기 도로 (B-ugv1 은 거기 없다)
    r = asyncio.run(B.evaluate({"task_id": "H", "decision_id": "D", "target_node": f"RP:{B.access.road_id}:{B.access.s:.1f}"}))
    assert r["verdict"] == "ACCEPT", r
    assert r["approach"]["spare_roads_released"] == {"683400513": "B-ugv1 (대기 도로)"}
