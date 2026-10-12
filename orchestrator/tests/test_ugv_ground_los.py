# -*- coding: utf-8 -*-
"""UGV 지상 열화상 — 지형 시선 모델 (ASSUMED_GROUND_LOS_V1, 기본, 2026-10-12).

UGV 는 도착 위치만 보고하고, 무엇이 보였는지는 총괄 모의 센서(observation.simulate_ground_los)가 환경 정답에서 읽는다.
반경 600 m 안은 항상 보이고, 600 m ~ 2 km 는 카메라(지면 + 3 m)에서 칸 지면까지 시선이 사이 지형에 막히지 않아야 보인다.
목표 칸을 못 보면 같은 도로 지점으로 다시 보내지 않고 보류한다.
"""
import math

import pytest

from orchestrator import config
from orchestrator.engine import Orchestrator
from orchestrator.env_adapter import FixtureEnv
from orchestrator.knowledge import InjectedAnalysis
from orchestrator.ledger import Ledger
from orchestrator.resources import UavClient, UgvClient

from .conftest import TARGET, submit
from .fakes import FakeUav, FakeUgv, normal_flight

REQ = {"resource_types": ["UGV"], "sensor": "THERMAL"}
N, MID, CELL_M = 51, 25, 90.0          # 51×51 칸(약 4.6 km) 격자, 가운데 칸(25_25) = 불난 목표 칸
DLAT = CELL_M / 111_320.0
RIDGE_ROW = MID + 10                   # 목표에서 남쪽 10칸(900 m) 줄에 능선을 세울 때


def _cells(ridge=False):
    dlon = CELL_M / (111_320.0 * math.cos(math.radians(TARGET["lat"])))
    fire, rest = [], []
    for c in range(N):
        for r in range(N):
            ground = 900.0 if ridge and r == RIDGE_ROW else 600.0
            cell = {"cell_id": f"{c}_{r}", "lat": TARGET["lat"] + (MID - r) * DLAT,
                    "lon": TARGET["lon"] + (c - MID) * dlon, "cell_size_m": CELL_M, "ground_amsl_m": ground}
            if (c, r) == (MID, MID):
                fire.append({**cell, "fire_state": "BURNING"})
            else:
                rest.append({**cell, "fire_state": "UNBURNED"})
    return fire, rest


def _world(tmp_path, ridge=False):
    fire, rest = _cells(ridge)
    env = FixtureEnv(fire_cells=fire, risk_cells=rest)
    uav, ugv = FakeUav(), FakeUgv()
    uav.default_script = normal_flight()
    ledger = Ledger(str(tmp_path / "state.sqlite3"))
    orch = Orchestrator(ledger, env, UavClient(uav.endpoints(), uav.client()), UgvClient("http://ugv", ugv.client()),
                        analysis=InjectedAnalysis())
    return {"ugv": ugv, "ledger": ledger, "orch": orch}


@pytest.fixture(autouse=True)
def thermal_on(monkeypatch):
    caps = dict(config.SIMULATED_CAPABILITIES)
    caps["UGV"] = tuple(dict.fromkeys(tuple(caps["UGV"]) + ("THERMAL",)))
    monkeypatch.setattr(config, "SIMULATED_CAPABILITIES", caps)


def _run(world, position, polls=4):
    orch, lg = world["orch"], world["ledger"]
    world["ugv"].default_script = lambda rid: [
        {"status": "IN_PROGRESS", "progress": {"phase": "ENROUTE"}},
        {"status": "COMPLETED", "progress": {"phase": "ARRIVED"},
         "observation": {"observation_type": "ROAD_STATUS", "arrived_node": "RP:test:0.0", "position": position},
         "_unit": {"state": "READY", "current_task_id": None}}]
    task = submit(orch, requirements=REQ, target={**TARGET, "cell_id": f"{MID}_{MID}"})
    out = orch.dispatch(task.task_id)
    for _ in range(polls):
        orch.poll()
    obs = [e["detail"] for e in lg.events(task.task_id)
           if e["event_type"] == "OBSERVATION" and (e["detail"] or {}).get("sensor_type") == "THERMAL"]
    return out, lg.get_task(task.task_id), obs


def _south(rows):
    return {"lat": TARGET["lat"] - rows * DLAT, "lon": TARGET["lon"]}


def test_default_ground_profile_is_terrain_los():
    p = config.SENSOR_PROFILES[config.GROUND_SENSOR_PROFILE_ID]
    assert config.GROUND_SENSOR_PROFILE_ID == "ASSUMED_GROUND_LOS_V1"
    assert (p["min_m"], p["max_m"], p["mast_m"]) == (600.0, 2000.0, 3.0)


def test_within_600m_always_seen(tmp_path):
    out, task, obs = _run(_world(tmp_path), _south(4))                # 360 m 남쪽
    assert out["resource_id"] == "A-ugv1" and len(obs) == 1
    o = obs[0]
    assert o["sensor_profile_id"] == "ASSUMED_GROUND_LOS_V1" and o["sensor_status"] == "TEST_ONLY"
    assert o["result"] == "DETECTED" and o["target_covered"]
    assert o["footprint"]["shape"] == "RADIUS_TERRAIN_LOS"
    assert task.purpose_status == "COMPLETED"


def test_flat_terrain_seen_up_to_2km(tmp_path):
    _, task, obs = _run(_world(tmp_path), _south(20))                 # 1.8 km 남쪽, 평지
    assert obs[0]["result"] == "DETECTED" and obs[0]["target_covered"]
    assert task.purpose_status == "COMPLETED"


def test_ridge_hides_target_and_holds_instead_of_redispatch(tmp_path):
    w = _world(tmp_path, ridge=True)
    _, task, obs = _run(w, _south(20), polls=8)                        # 1.8 km 남쪽, 사이 900 m 지점에 300 m 능선
    assert len(obs) == 1                                               # 같은 자리로 다시 보내지 않음
    o = obs[0]
    assert not o["target_covered"] and o["detections"] == [] and o["footprint"]["hidden_cells"] > 0
    assert task.purpose_status == "HOLD" and task.hold_reason == "GROUND_VIEW_TARGET_NOT_VISIBLE"


def test_beyond_2km_sees_nothing_of_target(tmp_path):
    _, task, obs = _run(_world(tmp_path), _south(24))                 # 2.16 km 남쪽
    assert obs[0]["result"] != "DETECTED" and not obs[0]["target_covered"]
    assert task.purpose_status != "COMPLETED"


def test_without_position_fails_without_inventing(tmp_path):
    _, task, obs = _run(_world(tmp_path), {"lat": None, "lon": None})
    assert obs[0]["result"] == "FAILED" and obs[0]["failure_reason"] == "POSITION_UNKNOWN"
    assert task.purpose_status != "COMPLETED"
