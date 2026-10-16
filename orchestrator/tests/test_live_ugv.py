# -*- coding: utf-8 -*-
"""실제 UGV Local Agent(ugv/server.py, UGV_DRIVER=sim) 와의 HTTP 계약 시험.

실행 전 (저장소 루트):
  UGV_DRIVER=sim UGV_TIME_SCALE=20 UGV_ALLOW_NO_FIRE_DATA=1 python -m uvicorn ugv.server:app --port 8100
  (UGV_TIME_SCALE=1 실시간이면 약 2.5 km 주행만으로 반납 대기(30 s)를 넘는다.
   UGV_ENV_URL 없이 돌리므로 UGV_ALLOW_NO_FIRE_DATA=1 이 없으면 FIRE_DATA_UNAVAILABLE 로 거절된다)
  ORCH_LIVE_UGV=1 python -m pytest orchestrator/tests/test_live_ugv.py -s

PX4 주행이 아니다. UGV 서버의 SimDriver(시연 속도)와 실제 도로망 판단을 검증한다.
"""

import math
import os
import time

import httpx
import pytest

from orchestrator.engine import Orchestrator
from orchestrator.env_adapter import FixtureEnv
from orchestrator.ledger import Ledger
from orchestrator.resources import UgvClient

pytestmark = pytest.mark.skipif(os.getenv("ORCH_LIVE_UGV") != "1", reason="실제 UGV 서버 필요")

URL = "http://127.0.0.1:8100"
ROAD_OK = {"lat": 38.07, "lon": 128.20, "cell_id": "ROAD_OK"}            # 도로 노드 약 530m
FAR_RIDGE = {"lat": 38.05, "lon": 128.25, "cell_id": "RIDGE"}            # 가장 가까운 노드가 2km 초과


def _wait_idle(timeout):
    deadline = time.time() + timeout
    while True:
        fleet = httpx.get(f"{URL}/ugv", timeout=5).json()
        busy = [u["resource_id"] for u in fleet if u["current_task_id"] is not None]
        if not busy:
            return fleet
        if time.time() >= deadline:
            pytest.fail(f"UGV 가 아직 임무 중이다: {busy} (UGV_TIME_SCALE 확인, 또는 서버 재시작)")
        time.sleep(0.5)


def _off_station_m(u):
    st, pos = u.get("station") or {}, u.get("position") or {}
    st = st.get("access_point") or st                    # 차량은 거점 좌표가 아니라 그 앞 도로 위 대기 지점에 선다
    if st.get("lat") is None or pos.get("lat") is None:
        return 0.0
    return math.hypot((pos["lat"] - st["lat"]) * 111_320, (pos["lon"] - st["lon"]) * 111_320 * math.cos(math.radians(st["lat"])))


@pytest.fixture(autouse=True)
def idle_vehicles():
    # 앞 시험(또는 앞 실행)의 차량이 아직 달리거나 목표 지점에 서 있으면 판정이 남은 상태에 좌우된다
    # (총괄 UGV 복귀는 기본 꺼짐 — 다시 돌리면 이미 그 자리라 주행 없이 도착으로 통과한다).
    # → 끝날 때까지 기다리고, 거점 밖 차량은 거점 대기 지점(station.access_point)으로 돌려보낸 뒤 시작한다.
    for u in _wait_idle(120):
        acc = (u.get("station") or {}).get("access_point") or {}
        if _off_station_m(u) > 30 and acc.get("road_id"):
            key = f"LIVE-HOME-{u['resource_id']}-{int(time.time() * 1000)}"
            httpx.post(f"{URL}/ugv/{u['resource_id']}/execute", timeout=10,
                       json={"task_id": key, "decision_id": key,
                             "target_node": f"RP:{acc['road_id']}:{float(acc['s_m']):.1f}"}).raise_for_status()
    off = [u["resource_id"] for u in _wait_idle(300) if _off_station_m(u) > 30]
    if off:
        pytest.fail(f"거점으로 돌아오지 못한 차량: {off}")
    yield


def _position(rid):
    return httpx.get(f"{URL}/ugv/{rid}/state", timeout=5).json()["position"]


def _moved_m(a, b):
    return math.hypot((b["lat"] - a["lat"]) * 111_320, (b["lon"] - a["lon"]) * 111_320 * math.cos(math.radians(a["lat"])))


def _orch(tmp_path, name):
    return Orchestrator(Ledger(str(tmp_path / f"{name}.db")), FixtureEnv(), ugv=UgvClient(URL))


def _submit(orch, rid, target, sensor="ROAD_STATUS", types=("UGV",)):
    task, _ = orch.submit_task({"request_id": rid, "incident_id": "INC-LIVE", "kind": "GROUND_RECON",
                                "target": dict(target),
                                "requirements": {"resource_types": list(types), "sensor": sensor,
                                                 "needs_env_ack": False}})
    return task


def _run_until_released(orch, attempt_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        orch.poll()
        if orch.ledger.get_attempt(attempt_id)["substatus"] == "RELEASED":
            return True
        time.sleep(0.5)
    return False


def test_live_ugv_road_status_closed_loop(tmp_path):
    orch = _orch(tmp_path, "ugv1")
    task = _submit(orch, "UGV-1", ROAD_OK)
    start = _position("A-ugv1")
    out = orch.dispatch(task.task_id)
    print("\ndispatch:", out)
    assert out["status"] == "STARTED" and out["resource_id"] == "A-ugv1"
    assert _run_until_released(orch, out["attempt_id"])
    # 실제로 달렸는지 (이미 목표에 서 있으면 경로 0 으로 도착 처리돼 시험이 거짓 통과한다): 위치 변화와 서버 경로 길이
    # 도착 위치는 임무 기록의 관측 위치로 잰다 (반납 시점 위치는 ORCH_UGV_RETURN_HOME=1 이면 거점 복귀 뒤라 0 에 가깝다)
    r = httpx.get(f"{URL}/ugv/A-ugv1/task/{out['attempt_id']}", timeout=5)
    r.raise_for_status()
    t = r.json()
    assert t["status"] == "COMPLETED", f"임무 상태 {t['status']}: {t.get('error')}"
    approach = t.get("approach") or {}
    total = (t.get("progress") or {}).get("total", 0)
    moved = _moved_m(start, t["observation"]["position"])
    print(f"moved {moved:.0f} m, route {approach.get('route_length_m')} m, progress total {total}")
    if "route_length_m" in approach:
        # ADAIR UGV 서버: 계획 경로 길이를 준다. progress.total 은 주행하면 드라이버 경로 점 수로 바뀌지만 경로 0 이면 1 로 남는다
        assert approach["route_length_m"] > 0, f"계획 경로 0 m — 주행 없이 도착 처리됨 (mode {approach.get('mode')}, point {approach.get('point')})"
    else:
        assert total > 0, f"서버 경로 waypoint 0 — 주행 없이 도착 처리됨: {t.get('progress')}"
    assert moved > 100, f"출발 위치에서 {moved:.0f} m 만 움직였다 — 주행 없이 도착 처리됨"
    ev = orch.ledger.events(task.task_id)
    for e in ev:
        print(" ", e["event_type"], e["resource_id"] or "", e["result"] or "", e["reason"] or "")
    obs = [e for e in ev if e["event_type"] == "OBSERVATION"][0]
    assert obs["result"] == "ROAD_STATUS" and obs["detail"]["is_fire_observation"] is False
    assert orch.ledger.get_task(task.task_id).purpose_status == "COMPLETED"
    assert orch.ledger.reservations() == {}


def test_live_ugv_unreachable_target_holds(tmp_path):
    orch = _orch(tmp_path, "ugv2")
    out = orch.dispatch(_submit(orch, "UGV-2", FAR_RIDGE).task_id)
    print("\n", out)
    assert out["status"] == "HOLD"
    assert out["excluded"]["A-ugv1"] == "LOCAL_REJECT:TARGET_UNREACHABLE"
    # 소방차(A-fire1·B-fire1)는 자원 종류가 맞지 않아 빠진다
    assert out["excluded"].get("A-fire1", "TYPE_NOT_ALLOWED") == "TYPE_NOT_ALLOWED"


def test_live_ugv_not_sent_for_thermal_task(tmp_path):
    orch = _orch(tmp_path, "ugv3")
    out = orch.dispatch(_submit(orch, "UGV-3", ROAD_OK, sensor="THERMAL", types=("UGV", "FIRE_ENGINE")).task_id)
    print("\n", out)
    assert out["status"] == "HOLD"
    assert set(out["excluded"].values()) == {"REQUIRED_CAPABILITY_UNAVAILABLE"}
    assert not any(e["event_type"] == "LOCAL_RESPONSE" for e in orch.ledger.events())


def test_live_two_tasks_do_not_share_vehicle(tmp_path):
    orch = _orch(tmp_path, "ugv4")
    a = orch.dispatch(_submit(orch, "UGV-4a", ROAD_OK).task_id)
    b = orch.dispatch(_submit(orch, "UGV-4b", ROAD_OK).task_id)
    print("\n", a, "\n", b)
    assert a["resource_id"] == "A-ugv1"
    assert b.get("resource_id") != "A-ugv1"          # 점유 중인 차는 두 번째 Task 후보에서 빠진다
    # 두 번째 Task 는 다른 거점 UGV(B-ugv1)가 멀리서 오거나, 그 차가 없는 서버 구성이면 HOLD 다
    assert b.get("resource_id") in (None, "B-ugv1")
    for r in (a, b):
        if r.get("attempt_id"):
            assert _run_until_released(orch, r["attempt_id"], timeout=180)
