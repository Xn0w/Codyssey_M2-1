# -*- coding: utf-8 -*-
"""Safety snapshot 버전 검사 완화 (config.SAFETY_SNAPSHOT_RECHECK, 트윈 한정 임시 — 사용자 결정 2026-10-19).
Local 평가 뒤 버전만 바뀌었으면 새 snapshot 으로 다시 확인하고, 가능 → 불가능이 됐을 때만 거절한다."""

import pytest

from orchestrator import config

from .conftest import submit


@pytest.fixture(autouse=True)
def recheck_on(monkeypatch):
    monkeypatch.setattr(config, "SAFETY_SNAPSHOT_RECHECK", True)


def _events(ledger, task_id, etype):
    return [e for e in ledger.events(task_id) if e["event_type"] == etype]


def _advance_after_first_eval(env, then=None):
    calls = {"n": 0}

    def v(body):
        calls["n"] += 1
        if calls["n"] == 1:
            env.advance()           # 평가 직후 시계만 진행 (트윈의 1분 틱)
            if then:
                then()
            return {"verdict": "ACCEPT", "eta_sec": 500}
        return v.later
    v.later = {"verdict": "ACCEPT", "eta_sec": 500}
    return v


def test_clock_only_change_is_rechecked_and_sent(world):
    orch, uav, env, lg = world["orch"], world["uav"], world["env"], world["ledger"]
    uav.verdicts["A-uav1"] = _advance_after_first_eval(env)
    task = submit(orch)
    out = orch.dispatch(task.task_id)
    assert out["status"] == "STARTED" and out["resource_id"] == "A-uav1"
    safeties = _events(lg, task.task_id, "SAFETY_JUDGEMENT")
    assert [s["result"] for s in safeties] == ["ALLOW"]               # SNAPSHOT_CHANGED 거절·재시작 없음
    rc = _events(lg, task.task_id, "SNAPSHOT_RECHECK")
    assert [r["result"] for r in rc] == ["STILL_FEASIBLE"]
    assert rc[0]["detail"]["to_state_version"] == rc[0]["detail"]["from_state_version"] + 1
    assert rc[0]["detail"]["local_recheck"]["verdict"] == "ACCEPT"            # 두 번째 Local 응답도 기록
    # 재확인은 같은 결정으로 Local 을 한 번 더 부른다
    evals = [c for c in uav.eval_calls() if c[1] == "A-uav1"]
    assert len(evals) == 2 and evals[0][3]["decision_id"] == evals[1][3]["decision_id"]
    assert len(uav.exec_calls()) == 1


def test_now_infeasible_after_change_is_refused_and_next_candidate_used(world):
    orch, uav, env, lg = world["orch"], world["uav"], world["env"], world["ledger"]
    v = _advance_after_first_eval(env)
    v.later = {"verdict": "REJECT", "reason": "LOW_BATTERY"}
    uav.verdicts["A-uav1"] = v
    task = submit(orch)
    out = orch.dispatch(task.task_id)
    assert out["status"] == "STARTED" and out["resource_id"] == "A-uav2"
    rc = _events(lg, task.task_id, "SNAPSHOT_RECHECK")
    assert rc[0]["result"] == "NOW_INFEASIBLE" and rc[0]["reason"] == "LOCAL_REJECT:LOW_BATTERY"
    assert all(c[1] != "A-uav1" for c in uav.exec_calls())


def test_mission_input_change_keeps_strict_reevaluation(world):
    orch, uav, env, lg = world["orch"], world["uav"], world["env"], world["ledger"]

    def wind_up():
        env.wind_ms = env.wind_ms + 1.0                 # 보낼 임무 조건(풍속)이 바뀜 → 처음부터 재평가
    uav.verdicts["A-uav1"] = _advance_after_first_eval(env, wind_up)
    task = submit(orch)
    out = orch.dispatch(task.task_id)
    assert out["status"] == "STARTED"
    assert _events(lg, task.task_id, "SNAPSHOT_RECHECK")[0]["result"] == "MISSION_INPUT_CHANGED"
    safeties = _events(lg, task.task_id, "SAFETY_JUDGEMENT")
    assert "SNAPSHOT_CHANGED" in safeties[0]["reason"] and safeties[-1]["result"] == "ALLOW"
    _, _, _, cmd = uav.exec_calls()[0]
    assert cmd["wind_ms"] == env.wind_ms                 # 새 풍속으로 평가한 명령


def test_flag_off_keeps_original_rejection(world, monkeypatch):
    monkeypatch.setattr(config, "SAFETY_SNAPSHOT_RECHECK", False)
    orch, uav, env, lg = world["orch"], world["uav"], world["env"], world["ledger"]
    uav.verdicts["A-uav1"] = _advance_after_first_eval(env)
    task = submit(orch)
    orch.dispatch(task.task_id)
    assert _events(lg, task.task_id, "SNAPSHOT_RECHECK") == []
    assert "SNAPSHOT_CHANGED" in _events(lg, task.task_id, "SAFETY_JUDGEMENT")[0]["reason"]
