# -*- coding: utf-8 -*-
# 작성: AI 코딩 도구(Claude Code)를 사용해 작성·검토한 코드다.
"""거점 복귀 지원(station.access_point, "RP:" 목적지)과 역제안(COUNTER, UGV_COUNTER=1).

실행 (저장소 루트):  python -m pytest tests/test_ugv_return_counter.py -q
UGV 서버(sim, 실제 도로망)를 띄워
  - 상태에 소속 거점과 거점 앞 도로 위 지점이 실리는지
  - 총괄 복귀가 보내는 형식 그대로("RP:도로ID:m") 실행하면 거점으로 돌아오는지, 거점에서 다시 보내면 바로 끝나는지
  - 기본(COUNTER 꺼짐)은 먼 목표를 지금처럼 거절하는지
  - COUNTER 를 켜면 같은 목표에 COUNTER 를 내고, counter_offer 를 실은 재평가·실행은 수락하는지
를 본다.
"""

import math
import os
import subprocess
import sys
import time

import httpx
import pytest

from tests.test_ugv_road_view import ROOT, _port, _stop

RID = "A-ugv1"
FAR = {"lat": 38.081984, "lon": 128.144513}      # 가장 가까운 도로·노드가 약 2.57 km (기준 2 km, COUNTER 상한 3 km)


def _start(state_dir, **extra):
    port = _port()
    env = {**os.environ, "UGV_DRIVER": "sim", "UGV_STATE_DIR": str(state_dir), "UGV_TIME_SCALE": "100",
           "UGV_SCENARIO": "", "UGV_REPORT_URL": "", "UGV_ORCH_URL": "http://127.0.0.1:9",
           "UGV_HISTORY_DIR": str(state_dir / "history"), "UGV_ENV_URL": "", **extra}
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "ugv.server:app", "--port", str(port), "--log-level", "warning"],
                         cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    url = f"http://127.0.0.1:{port}"
    end = time.time() + 40
    while time.time() < end:
        try:
            if httpx.get(url + "/health", timeout=1).status_code == 200:
                return p, url
        except httpx.HTTPError:
            time.sleep(0.3)
    p.kill()
    pytest.fail("UGV 서버 기동 실패: " + p.stderr.read().decode()[-500:])


def _m(a, b):
    return math.hypot((a[0] - b[0]) * 110540, (a[1] - b[1]) * 111320 * math.cos(math.radians(a[0])))


def _wait_done(url, tid, limit=90):
    end = time.time() + limit
    while time.time() < end:
        s = httpx.get(f"{url}/ugv/{RID}/task/{tid}").json()
        if s["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return s
        time.sleep(0.3)
    raise AssertionError(f"{tid} 가 끝나지 않음")


def _ev(url, tid, **body):
    return httpx.post(f"{url}/ugv/{RID}/evaluate", json={"task_id": tid, "decision_id": "D-" + tid, **body}).json()


def test_station_and_return_home(tmp_path):
    p, url = _start(tmp_path)
    try:
        st = httpx.get(f"{url}/ugv/{RID}/state").json()
        station = st["station"]
        acc = station["access_point"]
        assert station["base"] == "A" and station["node_id"] == "A"
        assert acc["road_id"] and acc["s_m"] >= 0 and acc["node_id"] == "A"
        assert _m((acc["lat"], acc["lon"]), (station["lat"], station["lon"])) < 1
        assert any(v["station"]["node_id"] == "B" for v in httpx.get(url + "/ugv").json())

        # 거점에서 1 km 남짓 떨어진 도로 위 지점으로 출동
        out = httpx.post(f"{url}/ugv/{RID}/execute", json={"task_id": "GO", "decision_id": "D1",
                                                            "target": {"lat": 38.07, "lon": 128.175}}).json()
        assert out["status"] == "STARTED", out
        assert _wait_done(url, "GO")["status"] == "COMPLETED"
        away = httpx.get(f"{url}/ugv/{RID}/state").json()
        assert _m((away["position"]["lat"], away["position"]["lon"]), (station["lat"], station["lon"])) > 300

        # 총괄 복귀와 같은 요청: target_node 만 "RP:도로ID:s_m"
        spec = f"RP:{acc['road_id']}:{float(acc['s_m']):.1f}"
        ev = _ev(url, "HOME-EV", target_node=spec)
        assert ev["verdict"] == "ACCEPT" and ev["stop_point"]["road_id"] == acc["road_id"], ev
        home = httpx.post(f"{url}/ugv/{RID}/execute", json={"task_id": "GO-HOME", "decision_id": "D1-HOME",
                                                             "target_node": spec}).json()
        assert home["status"] == "STARTED" and home["eta_sec"] > 0, home
        done = _wait_done(url, "GO-HOME")
        assert done["status"] == "COMPLETED", done
        st = httpx.get(f"{url}/ugv/{RID}/state").json()
        assert st["state"] == "READY" and st["current_task_id"] is None
        assert _m((st["position"]["lat"], st["position"]["lon"]), (station["lat"], station["lon"])) < 20

        # 거점에 서 있을 때 다시 보내면 움직이지 않고 바로 완료 (총괄 복귀 재요청·거점 대기)
        again = httpx.post(f"{url}/ugv/{RID}/execute", json={"task_id": "GO-HOME-2", "decision_id": "D2-HOME",
                                                              "target_node": spec}).json()
        assert again["eta_sec"] == 0
        assert httpx.get(f"{url}/ugv/{RID}/task/GO-HOME-2").json()["status"] == "COMPLETED"

        # 잘못된 지정
        bad = httpx.post(f"{url}/ugv/{RID}/evaluate", json={"task_id": "X", "decision_id": "D", "target_node": "RP:1"})
        assert bad.status_code == 422
        none = httpx.post(f"{url}/ugv/{RID}/evaluate", json={"task_id": "X", "decision_id": "D",
                                                              "target_node": "RP:NO_SUCH_ROAD:0"})
        assert none.status_code == 404
    finally:
        _stop(p)


def test_counter_off_by_default(tmp_path):
    p, url = _start(tmp_path)
    try:
        ev = _ev(url, "F1", target=FAR)
        assert ev["verdict"] == "REJECT" and ev["reason"] == "TARGET_UNREACHABLE", ev
        assert ev.get("counter_offer") is None
    finally:
        _stop(p)


def test_counter_offer_and_accept(tmp_path):
    p, url = _start(tmp_path, UGV_COUNTER="1")
    try:
        for mode in ("road_point", "node"):
            ev = _ev(url, "C-" + mode, target=FAR, target_mode=mode)
            assert ev["verdict"] == "COUNTER" and ev["reason"] == "TARGET_UNREACHABLE", ev
            offer = ev["counter_offer"]
            assert 2000 < offer["max_snap_m"] <= 3000 and offer["eta_sec"] > 0 and offer["note"]
            assert ev["eta_sec"] is None and ev["path"]

            # counter_offer 의 수정 필드를 그대로 실은 재평가 → 수락 (같은 지점)
            ok = _ev(url, "C2-" + mode, target=FAR, target_mode=mode, max_snap_m=offer["max_snap_m"])
            assert ok["verdict"] == "ACCEPT" and ok["eta_sec"] == offer["eta_sec"], ok

        # 상한(3 km)보다 먼 목표는 그대로 거절
        very_far = {"lat": FAR["lat"] + 0.05, "lon": FAR["lon"] - 0.05}
        assert _ev(url, "C3", target=very_far)["verdict"] == "REJECT"

        # 수용한 값으로 실행하면 출발한다
        offer = _ev(url, "C4", target=FAR)["counter_offer"]
        ex = httpx.post(f"{url}/ugv/{RID}/execute", json={"task_id": "C4-RUN", "decision_id": "D-C4",
                                                           "target": FAR, "max_snap_m": offer["max_snap_m"]})
        assert ex.status_code == 200 and ex.json()["status"] == "STARTED", ex.text
        # 수정값 없이 실행하면 지금처럼 거절 (409)
        httpx.post(f"{url}/ugv/{RID}/stop")
        plain = httpx.post(f"{url}/ugv/{RID}/execute", json={"task_id": "C5-RUN", "decision_id": "D-C5", "target": FAR})
        assert plain.status_code == 409
    finally:
        _stop(p)


# ---------------------------------------------------------------------------
# 총괄(orchestrator) 과 실제 UGV 서버를 함께 — 복귀 관리(ORCH_UGV_RETURN_HOME)·COUNTER 처리
# ---------------------------------------------------------------------------

def _orch(tmp_path, url):
    from orchestrator.engine import Orchestrator
    from orchestrator.env_adapter import FixtureEnv
    from orchestrator.ledger import Ledger
    from orchestrator.resources import UgvClient
    return Orchestrator(Ledger(str(tmp_path / "orch.db")), FixtureEnv(), ugv=UgvClient(url))


def _submit(orch, rid, target):
    task, _ = orch.submit_task({"request_id": rid, "incident_id": "INC-RET", "kind": "GROUND_RECON",
                                "target": dict(target),
                                "requirements": {"resource_types": ["UGV"], "sensor": "ROAD_STATUS",
                                                 "needs_env_ack": False}})
    return task


def test_orchestrator_return_home_with_real_ugv(tmp_path, monkeypatch):
    from orchestrator import config as oc
    monkeypatch.setattr(oc, "UGV_RETURN_HOME", True)
    p, url = _start(tmp_path)
    try:
        orch = _orch(tmp_path, url)
        out = orch.dispatch(_submit(orch, "RET-1", {"lat": 38.07, "lon": 128.175, "cell_id": "ROAD"}).task_id)
        assert out["status"] == "STARTED" and out["resource_id"] == RID, out
        aid = out["attempt_id"]
        subs, end = [], time.time() + 90
        while time.time() < end:
            orch.poll()
            s = orch.ledger.get_attempt(aid)["substatus"]
            if not subs or subs[-1] != s:
                subs.append(s)
            if s == "RELEASED":
                break
            time.sleep(0.3)
        assert subs[-1] == "RELEASED", subs
        assert "RETURNING" in subs
        rh = orch.ledger.get_attempt(aid)["detail"]["return_home"]
        assert rh["send"] == "ACK" and rh["last_status"] == "COMPLETED", rh
        st = httpx.get(f"{url}/ugv/{RID}/state").json()
        home = st["station"]
        assert _m((st["position"]["lat"], st["position"]["lon"]), (home["lat"], home["lon"])) < 20
    finally:
        _stop(p)


def test_orchestrator_drops_ugv_counter_like_reject(tmp_path):
    """총괄은 지금 UGV COUNTER 필드를 받지 않는다 → COUNTER 를 켜도 다음 후보로 넘기고 보류 (출동 없음)."""
    p, url = _start(tmp_path, UGV_COUNTER="1")
    try:
        orch = _orch(tmp_path, url)
        out = orch.dispatch(_submit(orch, "CNT-1", {**FAR, "cell_id": "FAR"}).task_id)
        assert out["status"] == "HOLD", out
        assert "A-ugv1" in out["excluded"] and "COUNTER" in out["excluded"]["A-ugv1"], out
        assert httpx.get(f"{url}/ugv/{RID}/state").json()["current_task_id"] is None
    finally:
        _stop(p)
