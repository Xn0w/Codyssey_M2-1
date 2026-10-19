# -*- coding: utf-8 -*-
"""/health 가 부를 때마다 판단 화면을 새로 만들지 않는지 (팀 트윈 시험 2026-10-19: 실행이 길어지면 1~10 s →
관제판 '연결 안 됨'·트윈 시계 막힘). 트윈 시계는 /llm/in_flight 로 LLM 대기만 확인한다."""

import time

from fastapi.testclient import TestClient

from orchestrator import config
from orchestrator.api import create_app


def _count_builds(orch, monkeypatch):
    n = {"builds": 0}
    real = orch._build_view

    def counted():
        n["builds"] += 1
        return real()
    monkeypatch.setattr(orch, "_build_view", counted)
    return n


def test_health_reuses_recent_view(world, monkeypatch):
    orch = world["orch"]
    c = TestClient(create_app(orch))
    n = _count_builds(orch, monkeypatch)
    h1 = c.get("/health").json()
    h2 = c.get("/health").json()
    h3 = c.get("/health").json()
    assert n["builds"] == 1                                    # 처음 한 번만 만든다
    assert h1["env"] == h2["env"] == h3["env"] and h1["env"]["source"] == "ORCHESTRATOR_VIEW"
    assert h3["env_view_age_s"] >= 0


def test_old_view_is_returned_at_once_and_refreshed_behind(world, monkeypatch):
    orch, env = world["orch"], world["env"]
    c = TestClient(create_app(orch))
    n = _count_builds(orch, monkeypatch)
    monkeypatch.setattr(config, "HEALTH_VIEW_MAX_AGE_S", 0.0)
    v0 = c.get("/health").json()["env"]["state_version"]      # 화면이 없으면 그 자리에서 만든다
    assert n["builds"] == 1
    env.advance()
    h = c.get("/health").json()
    assert h["env"]["state_version"] == v0                     # 낡은 화면을 바로 돌려준다 (기다리지 않음)
    deadline = time.monotonic() + 5
    while (n["builds"] < 2 or getattr(orch, "_view_refreshing", False)) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert n["builds"] == 2                                    # 새 화면은 뒤에서 하나만 만든다
    assert orch._last_view[1].state_version == env.state_version


def test_health_shows_view_made_by_engine(world, monkeypatch):
    orch, env = world["orch"], world["env"]
    c = TestClient(create_app(orch))
    env.advance()
    orch.view()                                                # 엔진이 판단하며 만든 화면
    n = _count_builds(orch, monkeypatch)
    h = c.get("/health").json()
    assert n["builds"] == 0 and h["env"]["state_version"] == env.state_version


def test_llm_in_flight_is_light(world, monkeypatch):
    orch = world["orch"]
    c = TestClient(create_app(orch))
    n = _count_builds(orch, monkeypatch)
    assert c.get("/llm/in_flight").json() == {"in_flight": 0}
    orch._llm_in_flight = 1
    assert c.get("/llm/in_flight").json() == {"in_flight": 1}
    assert n["builds"] == 0


def test_observation_summary_memo_matches_and_refreshes(world):
    from orchestrator.api import _observation_summary, observation_summary
    from .conftest import submit
    orch = world["orch"]
    t = submit(orch)
    orch.dispatch(t.task_id)
    for _ in range(3):
        orch.poll()
    a = observation_summary(orch, t.task_id)
    assert a == _observation_summary(orch, t.task_id)
    assert observation_summary(orch, t.task_id) is a           # 새 사건이 없으면 지난 결과
    orch.ledger.log("TASK_COMPLETE", task_id=t.task_id, result="X", detail={"marker": 1})
    b = observation_summary(orch, t.task_id)
    assert b is not a and b == _observation_summary(orch, t.task_id) and b["completion"] == {"marker": 1}
