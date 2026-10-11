# -*- coding: utf-8 -*-
"""총괄이 관리하는 UGV 복귀 (ORCH_UGV_RETURN_HOME, 2026-10-11 통합 시연 요청): 목적지 정차·READY 뒤 바로 반납하지 않고
소속 거점 대기 지점으로 복귀 실행 → 그 임무 완료 + READY 일 때만 반납. 복귀 중에는 점유 유지 (재배정 없음)."""
from orchestrator import config
from orchestrator.tests.conftest import submit


def _script(rid):
    return [{"status": "IN_PROGRESS", "progress": {"phase": "ENROUTE"}},
            {"status": "IN_PROGRESS", "progress": {"phase": "ENROUTE"}},
            {"status": "COMPLETED", "progress": {"phase": "DONE"}, "mission_result": "ARRIVED",
             "_unit": {"state": "READY", "current_task_id": None}}]


def test_ugv_returns_home_before_release(world, monkeypatch):
    monkeypatch.setattr(config, "UGV_RETURN_HOME", True)
    orch, ugv = world["orch"], world["ugv"]
    ugv.default_script = _script
    ugv.station = {"base_id": "A", "access_point": {"road_id": "682501660", "s_m": 46.8}}
    task = submit(orch, request_id="G1", kind="GROUND_SUPPORT",
                  requirements={"resource_types": ["UGV"], "sensor": None, "needs_env_ack": False})
    out = orch.dispatch(task.task_id)
    assert out["status"] == "STARTED" and out["resource_id"] == "A-ugv1", out
    aid = out["attempt_id"]
    subs = []
    for _ in range(12):
        orch.poll()
        subs.append(orch.ledger.get_attempt(aid)["substatus"])
    homes = [c for c in ugv.calls if c[0] == "POST" and c[1].endswith("/execute") and c[2]["task_id"].endswith("-HOME")]
    assert len(homes) == 1 and homes[0][2]["target_node"] == "RP:682501660:46.8"
    i_home = subs.index("RETURNING")
    assert "RELEASED" not in subs[:i_home + 1]                       # 복귀 실행 전·중에는 반납하지 않는다
    assert subs[-1] == "RELEASED"
    att = orch.ledger.get_attempt(aid)
    assert att["detail"]["return_home"]["last_status"] == "COMPLETED"
    assert orch.ledger.reservations() == [] or all(r.get("attempt_id") != aid for r in orch.ledger.reservations())


def test_return_refused_keeps_occupancy(world, monkeypatch):
    monkeypatch.setattr(config, "UGV_RETURN_HOME", True)
    orch, ugv = world["orch"], world["ugv"]
    ugv.default_script = _script
    ugv.station = None                                              # 대기 지점을 모르면 복귀를 보낼 수 없다
    task = submit(orch, request_id="G2", kind="GROUND_SUPPORT",
                  requirements={"resource_types": ["UGV"], "sensor": None, "needs_env_ack": False})
    aid = orch.dispatch(task.task_id)["attempt_id"]
    for _ in range(10):
        orch.poll()
    att = orch.ledger.get_attempt(aid)
    assert att["substatus"] == "RETURNING" and att["detail"]["return_home"]["status"] == "NO_ACCESS_POINT"
