"""관제판 응답 지연(묶음 4: /priority/board 9.33 s → 관제판 1.5 s 대기 초과로 '연결 안 됨')과
실행 이후 사건의 sim_time_s 미기록(도착 시각을 기록으로 확인 불가) 수정 시험."""
from fastapi.testclient import TestClient

from orchestrator.api import _board_observation, create_app, observation_summary
from orchestrator.ledger import ACTIVE

from .conftest import submit

AFTER_EXECUTION = ("EXECUTION_PROGRESS", "OBSERVATION", "ENVIRONMENT_APPLY", "TASK_COMPLETE")


def _run_recon(world, sim_s=1234.0):
    orch = world["orch"]
    world["env"].fire_cells[0]["cell_id"] = "C1"
    world["env"].simulation_time_s = sim_s
    t = submit(orch)
    orch.dispatch(t.task_id)
    for _ in range(3):
        orch.poll()
    return t


def test_events_after_execution_carry_sim_time(world):
    t = _run_recon(world, 1234.0)
    evs = [e for e in world["ledger"].events(t.task_id) if e["event_type"] in AFTER_EXECUTION]
    assert {e["event_type"] for e in evs} == set(AFTER_EXECUTION)
    assert all(e["sim_time_s"] == 1234.0 for e in evs), [(e["event_type"], e["sim_time_s"]) for e in evs]


def test_default_sim_time_does_not_override_or_leak(world):
    lg = world["ledger"]
    with lg.default_sim_time(50.0):
        a = lg.log("X_DEFAULT")
        b = lg.log("X_EXPLICIT", sim_time_s=7.0)
    c = lg.log("X_OUTSIDE")
    got = {e["seq"]: e["sim_time_s"] for e in lg.events()}
    assert (got[a], got[b], got[c]) == (50.0, 7.0, None)


def test_poll_without_work_does_not_read_env(world):
    env = world["env"]
    before = env.read_count
    world["orch"].poll()
    assert env.read_count == before


def test_last_event_matches_full_scan(world):
    _run_recon(world)
    lg = world["ledger"]
    for kind in ("EXECUTION_PROGRESS", "TASK_COMPLETE", "NO_SUCH_EVENT"):
        full = next((e for e in reversed(lg.events(run_id=ACTIVE)) if e["event_type"] == kind), None)
        assert lg.last_event(kind, run_id=ACTIVE) == full


def test_board_observation_keeps_only_partial_fractions():
    cc = [{"cell_id": "A", "full": True, "fraction": 1.0, "rect": [0, 0, 1, 1]},
          {"cell_id": "B", "full": False, "fraction": 0.25, "rect": [0, 0, 1, 1]}]
    o = {"result": "NOT_DETECTED", "covered_cells": ["A"], "partial_cells": ["B"], "cell_coverage": cc,
         "extras": [{"sensor_type": "WEATHER", "partial_cells": [], "cell_coverage": cc}]}
    s = _board_observation(o)
    assert s["cell_coverage"] == [{"cell_id": "B", "fraction": 0.25}] and s["covered_cells"] == ["A"]
    assert s["extras"][0]["cell_coverage"] == []
    assert o["cell_coverage"] is cc and len(cc) == 2                # 원본(장부·/tasks 응답)은 건드리지 않는다
    assert _board_observation(None) is None
    assert _board_observation({"result": "X", "cell_coverage": None})["cell_coverage"] is None


def test_board_results_equal_summary_except_coverage_detail(world):
    t = _run_recon(world)
    orch = world["orch"]
    c = TestClient(create_app(orch))
    r = c.get("/priority/board").json()["results"][0]
    full = c.get(f"/tasks/{t.task_id}").json()["observation"]
    assert r["task_id"] == t.task_id
    assert r["observation"] == _board_observation(full)
    assert full == observation_summary(orch, t.task_id)
