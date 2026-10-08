# -*- coding: utf-8 -*-
"""UGV 도로 상황판 — 실행 기록(ugv/history.py)과 상황판용 API.

실행 (저장소 루트):  python -m pytest tests/test_ugv_road_view.py -q
UGV 서버(sim, 실제 도로망)를 띄워 출동시키고, 서버를 다시 띄운 뒤 앞 실행이 과거 기록으로 남는지 본다.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _start(state_dir, scenario=""):
    port = _port()
    env = {**os.environ, "UGV_DRIVER": "sim", "UGV_STATE_DIR": str(state_dir), "UGV_TIME_SCALE": "100",
           "UGV_SCENARIO": scenario, "UGV_REPORT_URL": "", "UGV_ORCH_URL": "http://127.0.0.1:9"}
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


def _stop(p):
    p.terminate()
    try:
        p.wait(10)
    except subprocess.TimeoutExpired:
        p.kill()


def test_history_route_legs_and_past_run(tmp_path):
    p, url = _start(tmp_path, "ugv/scenarios/inje_girin.csv")
    try:
        run1 = httpx.get(url + "/history/runs").json()["current"]
        assert run1
        r = httpx.post(url + "/ugv/A-ugv1/execute", json={"task_id": "RV-1", "decision_id": "D1", "target_node": "B"})
        assert r.status_code == 200, r.text
        time.sleep(2)

        route = httpx.get(url + "/ugv/A-ugv1/route").json()
        legs = route["legs"]
        assert legs and all({"road_id", "distance_m", "travel_s", "congestion", "blocked", "state"} <= set(l) for l in legs)
        assert sum(l["state"] == "CURRENT" for l in legs) == 1
        assert [l["from"] for l in legs][1:] == [l["to"] for l in legs][:-1]      # 구간이 이어진다

        ev = httpx.get(f"{url}/history/runs/{run1}").json()["events"]
        types = [e["type"] for e in ev]
        assert types[0] == "RUN_START" and ev[0]["data"]["ugv_agent"] == "SEALED"
        assert "ROAD_STATE" in types and "UGV_TASK_STARTED" in types and "ROUTE" in types
        assert [e["seq"] for e in ev] == sorted(e["seq"] for e in ev)
        last = ev[-1]["seq"]
        more = httpx.get(f"{url}/history/runs/{run1}?after={last}").json()   # 이어 받기
        assert all(e["seq"] > last for e in more["events"])

        assert httpx.get(url + "/graph/bases").json()
        nodes = httpx.get(url + "/graph/nodes").json()
        assert len(nodes) > 100 and {"node_id", "lat", "lon", "degree"} <= set(nodes[0])
        # 총괄이 없으면 출동 요청은 실패 이유만 돌려준다 (서버는 멀쩡해야 한다)
        d = httpx.post(url + "/view/dispatch", json={"node_id": "B", "resource_type": "UGV"}, timeout=30).json()
        assert d["orch_http"] is None and d["request"]["requirements"] == {"resource_types": ["UGV"], "sensor": None}
        assert httpx.post(url + "/view/dispatch", json={"node_id": "B", "resource_type": "UAV"}).status_code == 422
        assert httpx.post(url + "/view/dispatch", json={"node_id": "nope", "resource_type": "UGV"}).status_code == 404
        assert httpx.get(url + "/view").status_code == 200
        assert httpx.get(url + "/history/runs/..%2Fugv_tasks").status_code == 404
    finally:
        _stop(p)

    p, url = _start(tmp_path)                    # 다시 띄우면 앞 실행은 과거 기록
    try:
        runs = httpx.get(url + "/history/runs").json()
        past = [r for r in runs["runs"] if not r["current"]]
        assert any(r["run_id"] == run1 and r["events"] > 3 and r["scenario"] == "inje_girin" for r in past)
        assert runs["current"] != run1
    finally:
        _stop(p)
