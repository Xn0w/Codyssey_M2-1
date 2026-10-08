# -*- coding: utf-8 -*-
"""도로 위 지점에 서기 (ugv/road_point.py) — 노드가 아닌 긴 도로 중간에서 계측.

실행 (저장소 루트):  python -m pytest tests/test_ugv_road_point.py -q
UGV 서버(sim, 실제 도로망)를 띄워 소방차를 도로 중간 지점으로 보내고, 그 자리에 서는지·같은 지점 재요청이
바로 끝나는지·지점 도로가 막히면 거절하는지·기본(노드) 방식은 그대로인지 본다.
"""

import math
import time

import httpx

from tests.test_ugv_road_view import _start, _stop

RID = "A-fire1"


def _m(a, b):
    return math.hypot((a[0] - b[0]) * 110540, (a[1] - b[1]) * 111320 * math.cos(math.radians(a[0])))


def _pick_road(url):
    """차 출발 노드에 닿지 않는 1 km 안팎 도로의 선형 중간점 — 가까운 것부터."""
    st = httpx.get(f"{url}/ugv/{RID}/state").json()
    here = (st["position"]["lat"], st["position"]["lon"])
    edges = {e["road_id"]: e for e in httpx.get(url + "/graph/edges").json()}
    best = None
    for r in httpx.get(url + "/roads/geometry").json()["roads"]:
        e, g = edges[r["road_id"]], r["geometry"]
        if not g or len(g) < 3 or not 600 <= e["distance_m"] <= 2000 or st["current_node"] in (e["a"], e["b"]):
            continue
        mid = g[len(g) // 2]
        d = _m(here, mid)
        if best is None or d < best[0]:
            best = (d, r["road_id"], mid, e)
    return best[1], best[2], best[3]


def _wait_done(url, tid, limit=60):
    end = time.time() + limit
    while time.time() < end:
        s = httpx.get(f"{url}/ugv/{RID}/task/{tid}").json()
        if s["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return s
        time.sleep(0.3)
    raise AssertionError(f"{tid} 가 끝나지 않음")


def test_stop_on_road_point(tmp_path):
    p, url = _start(tmp_path)
    try:
        road_id, mid, edge = _pick_road(url)
        target = {"lat": mid[0] + 0.0002, "lon": mid[1]}            # 도로에서 약 20 m 떨어진 계측 지점

        # 기본(노드) 방식은 그대로: stop_point 없이 노드로
        ev = httpx.post(f"{url}/ugv/{RID}/evaluate", json={"task_id": "N1", "decision_id": "D", "target": target}).json()
        assert ev["verdict"] == "ACCEPT" and ev["stop_point"] is None

        ev = httpx.post(f"{url}/ugv/{RID}/evaluate", json={"task_id": "P1", "decision_id": "D", "target": target,
                                                          "target_mode": "road_point"}).json()
        assert ev["verdict"] == "ACCEPT", ev
        sp = ev["stop_point"]
        assert sp["road_id"] == road_id and sp["snap_m"] < 40
        assert ev["target_node"]["node_id"] in (edge["a"], edge["b"])   # 지점 도로의 들어가는 끝 노드

        # 상황판 직접 명령(도로 위 지점) → 지점에 선다
        cmd = httpx.post(url + "/view/command", json={"resource_id": RID, "point": target}, timeout=30).json()
        assert cmd["verdict"] == "ACCEPT" and cmd["stop_point"]["road_id"] == road_id
        time.sleep(0.5)
        legs = httpx.get(f"{url}/ugv/{RID}/route").json().get("legs") or []
        assert legs and legs[-1]["to"] is None and legs[-1]["road_id"] == road_id and legs[-1]["to_point"]
        done = _wait_done(url, cmd["task_id"])
        assert done["status"] == "COMPLETED" and done["stop_point"]["road_id"] == road_id
        st = httpx.get(f"{url}/ugv/{RID}/state").json()
        assert _m((st["position"]["lat"], st["position"]["lon"]), (sp["lat"], sp["lon"])) < 15
        assert st["state"] == "READY" and st["current_node"] in (edge["a"], edge["b"])
        veh = {v["resource_id"]: v for v in httpx.get(url + "/view/vehicles", timeout=30).json()}
        assert veh[RID]["task"] is None and veh[RID]["place"]["point"] and veh[RID]["place"]["road_id"] == road_id

        # 같은 지점 다시 → 움직이지 않고 바로 도착 (붙박이 반복 관측)
        again = httpx.post(url + "/view/command", json={"resource_id": RID, "point": target}, timeout=30).json()
        assert again["verdict"] == "ACCEPT" and again["eta_sec"] == 0
        assert httpx.get(f"{url}/ugv/{RID}/task/{again['task_id']}").json()["status"] == "COMPLETED"

        # 도로 중간에 선 차가 다른 노드로 출발할 수 있다 (도로 중간 출발 규칙)
        other = edge["b"] if st["current_node"] == edge["a"] else edge["a"]
        go = httpx.post(url + "/view/command", json={"resource_id": RID, "node_id": other}, timeout=30).json()
        assert go["verdict"] == "ACCEPT"
        assert _wait_done(url, go["task_id"])["status"] == "COMPLETED"

        # 지점 도로가 막히면 그 지점엔 못 간다
        httpx.post(f"{url}/roads/{road_id}/block", json={"blocked": True})
        ev = httpx.post(f"{url}/ugv/{RID}/evaluate", json={"task_id": "P2", "decision_id": "D", "target": target,
                                                          "target_mode": "road_point"}).json()
        assert ev["verdict"] == "REJECT" and ev["reason"] == "ROAD_BLOCKED"
        httpx.post(f"{url}/roads/{road_id}/block", json={"blocked": False})

        # 총괄처럼 실행에 target + 평가가 준 target_node 를 같이 보내도 도로 위 지점으로 간다
        ex = httpx.post(f"{url}/ugv/{RID}/execute", json={"task_id": "P1X", "decision_id": "D", "target": target,
                                                         "target_node": edge["a"],
                                                         "target_mode": "road_point"}).json()
        assert ex["stop_point"]["road_id"] == road_id
        assert _wait_done(url, "P1X")["status"] == "COMPLETED"
        st = httpx.get(f"{url}/ugv/{RID}/state").json()
        assert _m((st["position"]["lat"], st["position"]["lon"]), (sp["lat"], sp["lon"])) < 15
    finally:
        _stop(p)
