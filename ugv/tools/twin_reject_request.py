# -*- coding: utf-8 -*-
# 작성: AI 코딩 도구(Claude Code)를 사용해 작성·검토한 코드다.
"""트윈 거절 시연 운용자 — 도로에서 2 km 넘게 먼 산속 칸으로 UGV 정찰을 총괄에 요청해 거절(TARGET_UNREACHABLE)을 받는다.

tools/twin_ground_dispatch.py 와 같은 '사람 역할' 스크립트다. 불 시나리오·도로 시나리오는 건드리지 않고
총괄 공식 API(POST /tasks) 로 요청 한 건만 더하고, 곧바로 배정을 요청한다(POST /tasks/{id}/dispatch).
총괄은 UGV 에 수행 가능성 평가를 보내고 거절을 받는다. 거절 기록(LOCAL_RESPONSE·TASK_HOLD)이 뜰 때까지 화면에 보여 준다.

    python ugv/tools/twin_reject_request.py                  # 지금 바로 한 번 요청 (수동)
    python ugv/tools/twin_reject_request.py --auto           # 시뮬레이션 40분이 지나면 한 번 요청하고 끝남 (자동)
    python ugv/tools/twin_reject_request.py --auto --at-min 60
    python ugv/tools/twin_reject_request.py --dry-run        # 요청하지 않고 고른 칸만 보여 줌

목적지 고르기
- 환경 서버 /map_cells 중 UGV 도로망(ugv/data/road_network.json)의 도로·노드 양쪽에서 --min-km(기본 2.2 km)보다 먼 칸.
- --pick near(기본): 그중 A 거점에 가장 가까운 칸 → 도로 상황판 지도 안에 보이고, 2 km 경계를 막 넘는 요청이 된다.
  --pick far: 도로에서 가장 먼 칸.
- 갈 수 있는지 판단은 UGV 서버가 한다(수락 거리 UGV_TARGET_SNAP_M, 기본 2 km). 이 스크립트는 요청만 한다.
- 실행(run) 하나에 한 번만 요청한다.
"""
import argparse
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ugv import graph_gpkg                      # noqa: E402  road_network.json → NODES, ROADS
from ugv.geo import distance_m                  # noqa: E402
from ugv.road_graph import RoadGraph            # noqa: E402
from ugv.road_point import nearest              # noqa: E402


def base_point() -> tuple[float, float]:
    """A 거점 좌표 (없으면 첫 노드)."""
    b = (graph_gpkg.BASES or {}).get("A")
    if isinstance(b, dict) and "lat" in b:
        return b["lat"], b["lon"]
    n = graph_gpkg.NODES[0]
    return n["lat"], n["lon"]


def pick_cell(cells: list, min_m: float, mode: str) -> tuple[dict, float]:
    """도로 위 점·노드 양쪽에서 min_m 보다 먼 칸 하나. (칸, 도로까지 거리 m)"""
    graph = RoadGraph(graph_gpkg.NODES, graph_gpkg.ROADS)
    nodes = [(n["lat"], n["lon"]) for n in graph_gpkg.NODES]
    home = base_point()
    cand = []
    for c in cells:
        lat, lon = c.get("lat"), c.get("lon")
        if lat is None or lon is None:
            continue
        d_node = min(distance_m((lat, lon), p) for p in nodes)
        if d_node > min_m:                       # 노드 거리로 먼저 거른 뒤에만 도로 선형 거리 계산 (느림)
            key = distance_m((lat, lon), home) if mode == "near" else -d_node
            cand.append((key, c))
    cand.sort(key=lambda x: x[0])
    for _, c in cand:
        rp = nearest(graph, c["lat"], c["lon"])
        d_road = rp.snap_m if rp else float("inf")
        if d_road > min_m:
            return c, d_road
    raise SystemExit(f"도로·노드에서 {min_m / 1000:.1f} km 넘게 먼 칸이 없음")


def request(cx: httpx.Client, orch: str, c: dict, wait_s: float) -> None:
    """요청 → 바로 배정 시도(POST /tasks/{id}/dispatch, 총괄 공식 API) → 거절이 기록될 때까지 보여 줌."""
    body = {"request_id": f"OPERATOR-REJECT:{c['cell_id']}", "incident_id": "INC-INJE-2019",
            "kind": "RECON",
            "target": {k: c.get(k) for k in ("lat", "lon", "ground_amsl_m", "cell_id")},
            "requirements": {"resource_types": ["UGV"], "sensor": "THERMAL"}}
    r = cx.post(f"{orch}/tasks", json=body)
    print(f"총괄 /tasks 거절 시연 요청 (칸 {c['cell_id']}) → HTTP {r.status_code}", flush=True)
    tid = ((r.json() if r.headers.get("content-type", "").startswith("application/json") else {}).get("task") or {}).get("task_id")
    if not tid:
        print(r.text[:300], flush=True)
        return
    # 총괄은 새 요청을 다음 시계 단계에서 배정한다. 관측 계획(LLM)이 도는 동안 시계가 서 있으면 수십 초 걸리므로 바로 배정을 요청한다
    try:
        d = cx.post(f"{orch}/tasks/{tid}/dispatch", timeout=120).json()
        print(f"배정 요청 → {d.get('status')} {d.get('reason') or ''}", flush=True)
    except (httpx.HTTPError, ValueError) as e:
        print(f"배정 요청 실패 ({e.__class__.__name__}) — 총괄의 다음 시계 단계를 기다림", flush=True)
    seen, t0 = 0, time.monotonic()
    while time.monotonic() - t0 < wait_s:
        try:
            evs = cx.get(f"{orch}/tasks/{tid}/events", params={"after_seq": seen}).json()
        except (httpx.HTTPError, ValueError):
            evs = []
        for e in evs if isinstance(evs, list) else []:
            seen = max(seen, int(e.get("seq") or 0))
            if e.get("event_type") in ("LOCAL_RESPONSE", "TASK_HOLD"):
                print(f"  {e.get('event_type')} {e.get('resource_id') or ''} {e.get('result')} {e.get('reason')}", flush=True)
                if e.get("event_type") == "TASK_HOLD":
                    return
        time.sleep(1.0)
    print(f"{wait_s:.0f}초 안에 거절 기록 없음 — 총괄 /tasks/{tid}/events 확인", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="http://127.0.0.1:8300")
    ap.add_argument("--orch", default="http://127.0.0.1:8200")
    ap.add_argument("--min-km", type=float, default=2.2, help="도로·노드에서 이보다 먼 칸만 후보 (수락 거리 2 km 초과)")
    ap.add_argument("--pick", choices=("near", "far"), default="near")
    ap.add_argument("--auto", action="store_true", help="시뮬레이션 시각이 --at-min 을 넘으면 한 번 요청하고 끝남")
    ap.add_argument("--at-min", type=float, default=40.0, help="자동 요청 시각 (시뮬레이션 분, 기본 40 = 첫 UGV 출동 뒤)")
    ap.add_argument("--wait-s", type=float, default=90.0, help="요청 뒤 거절 기록을 기다리는 시간 (실제 초)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cx = httpx.Client(timeout=30)
    if a.auto:
        print(f"거절 시연 운용자 대기: 시뮬레이션 {a.at_min:.0f}분에 한 번 요청", flush=True)
        misses = 0
        while True:
            try:
                t = cx.get(f"{a.env}/snapshot").json()["simulation_time_s"]
                misses = 0
                if t >= a.at_min * 60:
                    break
            except (httpx.HTTPError, KeyError, ValueError, TypeError):
                misses += 1
                if misses > 300:                  # 환경이 5분 넘게 없으면 (트윈을 껐으면) 그냥 끝냄
                    raise SystemExit("환경 서버 응답 없음 — 거절 요청 안 함")
            time.sleep(1.0)

    cells = cx.get(f"{a.env}/map_cells").json()["cells"]
    c, d_road = pick_cell(cells, a.min_km * 1000, a.pick)
    print(f"고른 칸 {c['cell_id']} ({c['lat']:.5f}, {c['lon']:.5f}) — 도로까지 {d_road / 1000:.2f} km", flush=True)
    if not a.dry_run:
        request(cx, a.orch, c, a.wait_s)


if __name__ == "__main__":
    main()
