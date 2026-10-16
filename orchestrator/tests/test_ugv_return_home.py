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
    assert "A-ugv1" not in orch.ledger.reservations()                 # 예약 해제
    assert "RETURNING" in subs[i_home:subs.index("RELEASED")]            # 복귀 임무 진행 중에는 RETURNING 으로 점유


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
    # 2026-10-16: 대기 지점 없음은 실패 확인 → FAULTED (점유 유지, 운용자 확인으로만 반납)
    assert att["substatus"] == "FAULTED" and att["detail"]["return_home"]["status"] == "NO_ACCESS_POINT"
    assert att["detail"]["return_home"]["failure"] == "NO_ACCESS_POINT"
    assert orch.ledger.reservations()["A-ugv1"]["attempt_id"] == aid


def test_queued_order_stop_skips_return_home(world, monkeypatch):
    """작업 지시서 다음 지점이 기다리면 거점에 들르지 않고 반납 (건식 예행연습: 지점마다 거점 왕복하던 것)."""
    monkeypatch.setattr(config, "UGV_RETURN_HOME", True)
    monkeypatch.setattr(config, "OBS_PLANNER_ENABLED", True)
    orch, ugv = world["orch"], world["ugv"]
    ugv.default_script = _script
    ugv.station = {"base_id": "A", "access_point": {"road_id": "682501660", "s_m": 46.8}}
    task = submit(orch, request_id="G3", kind="GROUND_SUPPORT",
                  requirements={"resource_types": ["UGV"], "sensor": None, "needs_env_ack": False})
    aid = orch.dispatch(task.task_id)["attempt_id"]
    monkeypatch.setattr(orch, "_queued_stop", lambda rid: True)
    for _ in range(8):
        orch.poll()
    assert orch.ledger.get_attempt(aid)["substatus"] == "RELEASED"
    assert not [c for c in ugv.calls if c[0] == "POST" and c[1].endswith("/execute") and c[2]["task_id"].endswith("-HOME")]


# ---------------------------------------------------------------------------
# 귀소 실패 예외 (2026-10-16): 실패 확인 → FAULTED, 불명 → UNKNOWN(재전송 없음), 둘 다 점유 유지.
# 운용자 CONFIRM_RESOURCE_IDLE 은 UNKNOWN·FAULTED 에서만 반납, 정상 RETURNING 에서는 거절.
# ---------------------------------------------------------------------------
import httpx                                                              # noqa: E402

STATION = {"base_id": "A", "access_point": {"road_id": "682501660", "s_m": 46.8}}


def _run_to_return_stage(world, monkeypatch, hook=None, polls=12, rid_req="GX"):
    monkeypatch.setattr(config, "UGV_RETURN_HOME", True)
    orch, ugv = world["orch"], world["ugv"]
    ugv.default_script = _script
    ugv.station = STATION
    ugv.hook = hook
    ugv.units["A-ugv1"].update(state="READY", current_task_id=None)    # 앞 경우에서 운용자가 정지를 확인한 차량
    task = submit(orch, request_id=rid_req, kind="GROUND_SUPPORT",
                  requirements={"resource_types": ["UGV"], "sensor": None, "needs_env_ack": False})
    aid = orch.dispatch(task.task_id)["attempt_id"]
    for _ in range(polls):
        orch.poll()
    return orch, ugv, task, aid


def _home_execs(ugv, aid):
    return [c for c in ugv.calls if c[0] == "POST" and c[1].endswith("/execute") and c[2]["task_id"] == f"{aid}-HOME"]


def _held(orch, aid):
    r = orch.ledger.reservations().get("A-ugv1")
    return bool(r) and r["attempt_id"] == aid


def _home_status(status):
    """복귀 임무(-HOME) 조회만 status 로 응답한다."""
    def hook(method, path, body):
        if method == "GET" and path.endswith("-HOME"):
            if isinstance(status, int):
                return httpx.Response(status, json={"detail": "x"})
            return httpx.Response(200, json={"task_id": path.rsplit("/", 1)[1], "resource_id": "A-ugv1",
                                             "status": status, "progress": {"phase": status}, "observation": None,
                                             "error": "x" if status != "IN_PROGRESS" else None})
        return None
    return hook


def _home_execute(code):
    def hook(method, path, body):
        if method == "POST" and path.endswith("/execute") and body["task_id"].endswith("-HOME"):
            return httpx.Response(code, json={"detail": "refused" if code < 500 else "gateway"})
        return None
    return hook


def test_home_execute_refused_faults_and_keeps_occupancy(world, monkeypatch):
    orch, ugv, task, aid = _run_to_return_stage(world, monkeypatch, _home_execute(409))
    att = orch.ledger.get_attempt(aid)
    assert att["substatus"] == "FAULTED" and att["detail"]["return_home"]["failure"] == "EXECUTE_REFUSED"
    assert _held(orch, aid) and len(_home_execs(ugv, aid)) == 1             # 거절 뒤 다시 보내지 않는다
    assert any(e["event_type"] == "UGV_RETURN_HOME_FAILED" for e in orch.ledger.events(task.task_id))


def test_home_task_failed_or_cancelled_faults(world, monkeypatch):
    for st in ("FAILED", "CANCELLED"):
        orch, ugv, task, aid = _run_to_return_stage(world, monkeypatch, _home_status(st), rid_req=f"G-{st}")
        att = orch.ledger.get_attempt(aid)
        assert att["substatus"] == "FAULTED", (st, att["substatus"])
        assert att["detail"]["return_home"]["failure"] == f"TASK_{st}"
        assert _held(orch, aid) and len(_home_execs(ugv, aid)) == 1
        world["orch"].resolve(task.task_id, "CONFIRM_RESOURCE_IDLE", "test cleanup", attempt_id=aid)


def test_home_send_unknown_is_unknown_without_resend(world, monkeypatch):
    orch, ugv, task, aid = _run_to_return_stage(world, monkeypatch, _home_execute(502), polls=20)
    att = orch.ledger.get_attempt(aid)
    assert att["substatus"] == "UNKNOWN" and att["detail"]["unknown_reason"] == "UGV_RETURN_HOME_UNKNOWN:SEND_UNKNOWN"
    assert _held(orch, aid)
    assert len(_home_execs(ugv, aid)) == 1                                   # 재전송 0회 (20번 조회 동안)
    ev = orch.ledger.events(task.task_id)
    assert sum(1 for e in ev if e["event_type"] == "OBSERVATION") == 1                 # 원 임무 재관측 없음
    assert not [e for e in ev if e["reason"] == "PROVIDER_RECONTACTED"]                # 원 임무 응답으로 되살리지 않음
    assert orch.ledger.open_mission_attempts(task.task_id) == []                       # 임무는 닫힘 (점유만 유지)


def test_home_status_not_found_or_unreachable_is_unknown(world, monkeypatch):
    orch, ugv, task, aid = _run_to_return_stage(world, monkeypatch, _home_status(404), rid_req="G-404")
    att = orch.ledger.get_attempt(aid)
    assert att["substatus"] == "UNKNOWN" and att["detail"]["unknown_reason"] == "UGV_RETURN_HOME_UNKNOWN:NOT_FOUND"
    assert _held(orch, aid) and len(_home_execs(ugv, aid)) == 1
    orch.resolve(task.task_id, "CONFIRM_RESOURCE_IDLE", "cleanup", attempt_id=aid)
    # 잠깐 끊김은 RESOURCE_OFFLINE_S 동안 RETURNING 으로 기다리고, 넘으면 UNKNOWN
    monkeypatch.setattr(config, "RESOURCE_OFFLINE_S", 3600.0)
    orch, ugv, task, aid = _run_to_return_stage(world, monkeypatch, _home_status(503), rid_req="G-503a")
    assert orch.ledger.get_attempt(aid)["substatus"] == "RETURNING" and _held(orch, aid)
    monkeypatch.setattr(config, "RESOURCE_OFFLINE_S", 0.0)
    orch.poll()
    att = orch.ledger.get_attempt(aid)
    assert att["substatus"] == "UNKNOWN" and att["detail"]["unknown_reason"] == "UGV_RETURN_HOME_UNKNOWN:UNREACHABLE"
    assert _held(orch, aid) and len(_home_execs(ugv, aid)) == 1


def test_home_unknown_recovers_when_task_reported_again(world, monkeypatch):
    """송신 응답은 잃었지만 명령은 실제로 갔다 → 같은 실행 키로 조회가 되면 추적 재개 → 완료·READY 에 정상 반납."""
    state = {"lost": True}

    def hook(method, path, body):
        if method == "POST" and path.endswith("/execute") and body["task_id"].endswith("-HOME"):
            ugv = world["ugv"]                                           # 명령은 도착시키고 응답만 잃는다
            ugv.units["A-ugv1"].update(current_task_id=body["task_id"], state="RUNNING")
            ugv.scripts[body["task_id"]] = _script("A-ugv1")
            return httpx.Response(502, json={"detail": "lost"})
        if method == "GET" and path.endswith("-HOME") and state["lost"]:
            return httpx.Response(404, json={"detail": "x"})
        return None
    orch, ugv, task, aid = _run_to_return_stage(world, monkeypatch, hook, polls=10)
    assert orch.ledger.get_attempt(aid)["substatus"] == "UNKNOWN"
    state["lost"] = False
    subs = []
    for _ in range(8):
        orch.poll()
        subs.append(orch.ledger.get_attempt(aid)["substatus"])
    assert "RETURNING" in subs and subs[-1] == "RELEASED", subs
    assert len(_home_execs(ugv, aid)) == 1 and not _held(orch, aid)
    assert any(e["event_type"] == "UGV_RETURN_HOME_RECONTACTED" for e in orch.ledger.events(task.task_id))


def test_confirm_idle_releases_faulted_and_unknown_but_not_returning(world, monkeypatch):
    # FAULTED → 반납
    orch, ugv, task, aid = _run_to_return_stage(world, monkeypatch, _home_execute(409), rid_req="G-F")
    before = orch.ledger.get_task(task.task_id).purpose_status
    assert before == "COMPLETED"                                          # 목적은 이미 끝났고 차량만 점유 중
    out = orch.resolve(task.task_id, "CONFIRM_RESOURCE_IDLE", "운용자 정지 확인", attempt_id=aid)
    att = orch.ledger.get_attempt(aid)
    assert out["status"] == "RELEASED" and att["substatus"] == "FAILED" and not _held(orch, aid)
    assert att["detail"]["manual_idle_confirmed"] is True and att["detail"]["previous_substatus"] == "FAULTED"
    assert att["detail"]["manual_reason"] == "운용자 정지 확인"
    assert orch.ledger.get_task(task.task_id).purpose_status == before    # 종료된 목적은 되살리지 않는다
    # 귀소 UNKNOWN → 반납
    orch, ugv, task, aid = _run_to_return_stage(world, monkeypatch, _home_execute(502), rid_req="G-U")
    before = orch.ledger.get_task(task.task_id).purpose_status
    assert before == "COMPLETED"
    out = orch.resolve(task.task_id, "CONFIRM_RESOURCE_IDLE", "확인", attempt_id=aid)
    att = orch.ledger.get_attempt(aid)
    assert out["status"] == "RELEASED" and att["substatus"] == "FAILED" and not _held(orch, aid)
    assert att["detail"]["previous_substatus"] == "UNKNOWN" and att["detail"]["manual_idle_confirmed"] is True
    assert att["detail"]["manual_reason"] == "확인"
    assert orch.ledger.get_task(task.task_id).purpose_status == before
    # 정상 RETURNING → 거절, 점유 유지
    orch, ugv, task, aid = _run_to_return_stage(world, monkeypatch, _home_status("IN_PROGRESS"), rid_req="G-R")
    assert orch.ledger.get_attempt(aid)["substatus"] == "RETURNING"
    out = orch.resolve(task.task_id, "CONFIRM_RESOURCE_IDLE", "실수", attempt_id=aid)
    assert out["status"] == "REFUSED" and out["reason"] == "ATTEMPT_NOT_UNKNOWN_OR_FAULTED"
    assert orch.ledger.get_attempt(aid)["substatus"] == "RETURNING" and _held(orch, aid)


def test_confirm_idle_keeps_cancelled_task_cancelled(world, monkeypatch):
    """12: 주행 중 목적을 취소한 Task(CANCELLED)는 귀소 실패 → 수동 자원 해제 뒤에도 되살아나지 않는다."""
    orch, ugv, task, aid = _run_to_return_stage(world, monkeypatch, _home_execute(409), polls=0, rid_req="G-C")
    orch.poll()                                                           # 아직 주행 중
    assert orch.resolve(task.task_id, "CANCEL", "운용자 취소")["status"] != "REFUSED"
    assert orch.ledger.get_task(task.task_id).purpose_status == "CANCELLED"
    for _ in range(12):
        orch.poll()                                                       # 차량은 끝까지 가서 귀소 시도 → 거절
    assert orch.ledger.get_attempt(aid)["substatus"] == "FAULTED" and _held(orch, aid)
    out = orch.resolve(task.task_id, "CONFIRM_RESOURCE_IDLE", "정지 확인", attempt_id=aid)
    assert out["status"] == "RELEASED" and not _held(orch, aid)
    assert orch.ledger.get_task(task.task_id).purpose_status == "CANCELLED"


def test_home_unknown_survives_bad_original_response(world, monkeypatch):
    """귀소 불명 중 원 임무 응답이 형식 오류여도 귀소 임무로 판단해 복구된다 (원 임무 응답 검증에 막히지 않음)."""
    state = {"phase": "lost"}

    def hook(method, path, body):
        if method == "POST" and path.endswith("/execute") and body["task_id"].endswith("-HOME"):
            u = world["ugv"]
            u.units["A-ugv1"].update(current_task_id=body["task_id"], state="RUNNING")
            u.scripts[body["task_id"]] = _script("A-ugv1")
            return httpx.Response(502, json={"detail": "lost"})
        if method == "GET" and path.endswith("-HOME") and state["phase"] == "lost":
            return httpx.Response(404, json={"detail": "x"})
        if method == "GET" and "/task/" in path and not path.endswith("-HOME") and state["phase"] == "bad":
            return httpx.Response(200, json={"task_id": path.rsplit("/", 1)[1], "status": "COMPLETED"})   # resource_id 없음
        return None
    orch, ugv, task, aid = _run_to_return_stage(world, monkeypatch, hook, polls=10)
    assert orch.ledger.get_attempt(aid)["substatus"] == "UNKNOWN"
    state["phase"] = "bad"
    for _ in range(8):
        orch.poll()
    assert orch.ledger.get_attempt(aid)["substatus"] == "RELEASED"
    assert len(_home_execs(ugv, aid)) == 1


def test_faulted_stays_faulted_when_original_task_lost_or_setting_off(world, monkeypatch):
    """FAULTED(귀소 실패 확인)는 원 임무 조회 404·서버 끊김이나 귀소 설정 끄기로 바뀌거나 반납되지 않는다."""
    lost = {"on": False}
    base = _home_execute(409)

    def hook(method, path, body):
        r = base(method, path, body)
        if r is not None:
            return r
        if lost["on"] and method == "GET" and "/task/" in path:
            return httpx.Response(404, json={"detail": "x"})
        return None
    orch, ugv, task, aid = _run_to_return_stage(world, monkeypatch, hook)
    assert orch.ledger.get_attempt(aid)["substatus"] == "FAULTED"
    lost["on"] = True
    monkeypatch.setattr(config, "RESOURCE_OFFLINE_S", 0.0)
    for _ in range(4):
        orch.poll()
    assert orch.ledger.get_attempt(aid)["substatus"] == "FAULTED" and _held(orch, aid)
    lost["on"] = False
    monkeypatch.setattr(config, "UGV_RETURN_HOME", False)
    world["ugv"].units["A-ugv1"].update(state="READY", current_task_id=None)
    for _ in range(4):
        orch.poll()
    assert orch.ledger.get_attempt(aid)["substatus"] == "FAULTED" and _held(orch, aid)


def test_home_unknown_does_not_block_handover_of_reopened_task(world, monkeypatch):
    """귀소 불명 시도는 임무가 끝난 시도라 같은 Task 의 재배정을 막지 않는다 (차량 점유는 유지)."""
    orch, ugv, task, aid = _run_to_return_stage(world, monkeypatch, _home_execute(502), rid_req="G-H")
    assert orch.ledger.get_attempt(aid)["substatus"] == "UNKNOWN" and _held(orch, aid)
    assert orch.ledger.open_mission_attempts(task.task_id) == []


def test_confirm_on_return_home_unknown_does_not_touch_other_hold(world, monkeypatch):
    """귀소 불명 시도는 목적을 보류시키지 않았다 → 그 시도를 수동 해제해도 다른 이유의 HOLD 를 PENDING 으로 바꾸지 않는다."""
    monkeypatch.setattr(config, "UGV_RETURN_HOME", True)
    orch, ugv = world["orch"], world["ugv"]
    ugv.default_script = _script
    task = submit(orch, request_id="G-HOLD", kind="GROUND_SUPPORT",
                  requirements={"resource_types": ["UGV"], "sensor": None, "needs_env_ack": False})
    aid = orch.dispatch(task.task_id)["attempt_id"]
    t = orch.ledger.get_task(task.task_id)
    orch._set_purpose(t, "HOLD", basis="EXECUTION_UNKNOWN:OTHER_ATTEMPT", hold_reason="OTHER_ATTEMPT_OFFLINE",
                      resume="MANUAL_RESOLUTION")                         # 다른 시도 때문에 보류된 목적
    att = orch.ledger.get_attempt(aid)
    orch.ledger.set_attempt_status(aid, "UNKNOWN", {**(att["detail"] or {}), "mission_end": {"reason": "X"},
                                                    "unknown_reason": "UGV_RETURN_HOME_UNKNOWN:SEND_UNKNOWN",
                                                    "pre_unknown_substatus": "RETURNING"})
    out = orch.resolve(task.task_id, "CONFIRM_RESOURCE_IDLE", "정지 확인", attempt_id=aid)
    assert out["status"] == "RELEASED" and not _held(orch, aid)
    t = orch.ledger.get_task(task.task_id)
    assert t.purpose_status == "HOLD" and t.hold_reason == "OTHER_ATTEMPT_OFFLINE"


def test_fire_engine_does_not_return_home(world, monkeypatch):
    """귀소는 UGV 만 (2026-10-16): 소방차는 도착 위치에 머물고(마을회관 방어 등) READY 확인으로 반납된다."""
    monkeypatch.setattr(config, "UGV_RETURN_HOME", True)
    orch, ugv = world["orch"], world["ugv"]
    ugv.default_script = _script
    ugv.station = STATION
    ugv.units["A-ugv1"]["resource_type"] = "FIRE_ENGINE"
    task = submit(orch, request_id="FE1", kind="GROUND_SUPPORT",
                  requirements={"resource_types": ["FIRE_ENGINE"], "sensor": None, "needs_env_ack": False})
    out = orch.dispatch(task.task_id)
    assert out["status"] == "STARTED", out
    aid = out["attempt_id"]
    assert orch.ledger.get_attempt(aid)["command"]["resource_type"] == "FIRE_ENGINE"
    for _ in range(8):
        orch.poll()
    att = orch.ledger.get_attempt(aid)
    assert att["substatus"] == "RELEASED" and "return_home" not in (att["detail"] or {})
    assert not _home_execs(ugv, aid) and not _held(orch, aid)
