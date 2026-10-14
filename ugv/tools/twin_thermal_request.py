# -*- coding: utf-8 -*-
# 작성: AI 코딩 도구(Claude Code)를 사용해 작성·검토한 코드다.
"""트윈 UGV 열화상 시연 운용자 — 지금 불타는 칸으로 UGV 전용 열화상 정찰을 총괄에 요청한다.

팀 main 트윈에서는 열화상 임무가 대부분 드론 전용(야간 순찰)이고, 신고 때 자동 정찰도 더 가까운 드론이 먼저 뽑혀
UGV 가 열화상으로 불릴 일이 거의 없다. 이 스크립트는 tools/twin_ground_dispatch.py 와 같은 '사람 역할'로,
불 시나리오는 건드리지 않고 총괄 공식 API(POST /tasks, resource_types=["UGV"])로 요청만 더한다.
어느 UGV 를 보낼지·갈 수 있는지는 총괄과 UGV 가 정하고(평가 → 출동), 도착 뒤 관측은 총괄 모의 열화상
(ASSUMED_GROUND_LOS_V1: 반경 600 m 상시, 2 km 까지 지형 시선)이 계산한다.

    python ugv/tools/twin_thermal_request.py                        # 지금 바로 한 건
    python ugv/tools/twin_thermal_request.py --auto                 # 시뮬레이션 20분부터 30분마다, 최대 6건
    python ugv/tools/twin_thermal_request.py --auto --start-min 10 --every-min 20 --count 8
    python ugv/tools/twin_thermal_request.py --dry-run              # 요청하지 않고 고른 칸만 보여 줌

목적지 고르기
- 환경 /snapshot 의 불 칸 중 UGV 도로망의 도로 위 점까지 --max-km(기본 1.9 km) 안인 칸. 불타는 칸(BURNING)이 먼저,
  불이 다 꺼졌으면 다 탄 칸(BURNED)으로 (열화상은 다 탄 칸도 탐지로 기록한다).
- 아직 요청하지 않은 칸 가운데 A·B 거점 중 가까운 쪽에서 가장 가까운 칸 (같은 칸은 한 번만).
"""
import argparse
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ugv import graph_gpkg                      # noqa: E402
from ugv.geo import distance_m                  # noqa: E402
from ugv.road_graph import RoadGraph            # noqa: E402
from ugv.road_point import nearest              # noqa: E402

GRAPH = RoadGraph(graph_gpkg.NODES, graph_gpkg.ROADS)
BASES = [(b["lat"], b["lon"]) for b in (graph_gpkg.BASES or {}).values() if isinstance(b, dict) and "lat" in b]


def pick_cell(fire_cells: list, done: set, max_m: float):
    """도로에서 max_m 안이고 아직 요청 안 한 불 칸 하나. 불타는 칸(BURNING)이 먼저, 없으면 다 탄 칸(BURNED).
    (칸, 도로까지 m) 또는 None"""
    for state in ("BURNING", "BURNED"):
        cand = []
        for c in fire_cells:
            if c.get("fire_state") != state or c.get("lat") is None or c["cell_id"] in done:
                continue
            home = min((distance_m((c["lat"], c["lon"]), b) for b in BASES), default=0.0)
            cand.append((home, c))
        for _, c in sorted(cand, key=lambda x: x[0]):
            rp = nearest(GRAPH, c["lat"], c["lon"])
            if rp is not None and rp.snap_m <= max_m:
                return c, rp.snap_m
    return None


def request(cx: httpx.Client, orch: str, c: dict, n: int, wait_s: float) -> None:
    body = {"request_id": f"OPERATOR-UGV-THERMAL:{c['cell_id']}:{n}", "incident_id": "INC-INJE-2019",
            "kind": "RECON",
            "target": {k: c.get(k) for k in ("lat", "lon", "ground_amsl_m", "cell_id")},
            "requirements": {"resource_types": ["UGV"], "sensor": "THERMAL"}}
    r = cx.post(f"{orch}/tasks", json=body)
    task = (r.json() if r.headers.get("content-type", "").startswith("application/json") else {}).get("task") or {}
    tid = task.get("task_id")
    print(f"[{n}] UGV 열화상 요청 칸 {c['cell_id']} → HTTP {r.status_code} {tid or r.text[:200]}", flush=True)
    if not tid:
        return
    seen, t0 = 0, time.monotonic()
    while time.monotonic() - t0 < wait_s:
        try:
            evs = cx.get(f"{orch}/tasks/{tid}/events", params={"after_seq": seen}).json()
        except (httpx.HTTPError, ValueError):
            evs = []
        for e in evs if isinstance(evs, list) else []:
            seen = max(seen, int(e.get("seq") or 0))
            et = e.get("event_type")
            if et in ("LOCAL_RESPONSE", "EXECUTION_SENT", "OBSERVATION", "TASK_COMPLETE", "TASK_HOLD"):
                print(f"    {et} {e.get('resource_id') or ''} {e.get('result') or ''} {e.get('reason') or ''}", flush=True)
            if et in ("TASK_COMPLETE", "TASK_HOLD"):
                return
        time.sleep(1.0)
    print(f"    {wait_s:.0f}초 안에 끝나지 않음 — 총괄 /tasks/{tid}/events 확인", flush=True)


def sim_time(cx: httpx.Client, env: str):
    try:
        return cx.get(f"{env}/snapshot").json()
    except (httpx.HTTPError, ValueError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="http://127.0.0.1:8300")
    ap.add_argument("--orch", default="http://127.0.0.1:8200")
    ap.add_argument("--max-km", type=float, default=1.9, help="도로 위 점까지 이 거리 안인 불 칸만 (UGV 수락 2 km 안쪽)")
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--start-min", type=float, default=20.0, help="첫 요청 시각 (시뮬레이션 분)")
    ap.add_argument("--every-min", type=float, default=30.0, help="요청 간격 (시뮬레이션 분)")
    ap.add_argument("--count", type=int, default=6, help="최대 요청 수")
    ap.add_argument("--wait-s", type=float, default=90.0, help="요청마다 결과를 기다리는 시간 (실제 초)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cx = httpx.Client(timeout=30)
    done, n, next_s, misses = set(), 0, a.start_min * 60, 0
    if a.auto:
        print(f"UGV 열화상 운용자 대기: 시뮬레이션 {a.start_min:.0f}분부터 {a.every_min:.0f}분마다, 최대 {a.count}건", flush=True)
    while n < (a.count if a.auto else 1):
        snap = sim_time(cx, a.env)
        if snap is None:
            misses += 1
            if misses > 300:
                raise SystemExit("환경 서버 응답 없음 — 끝냄")
            time.sleep(1.0)
            continue
        misses = 0
        if a.auto and snap.get("simulation_time_s", 0.0) < next_s:
            time.sleep(1.0)
            continue
        got = pick_cell(snap.get("fire_cells") or [], done, a.max_km * 1000)
        if got is None:
            states = {}
            for x in snap.get("fire_cells") or []:
                states[x.get("fire_state")] = states.get(x.get("fire_state"), 0) + 1
            print(f"시뮬레이션 {snap.get('simulation_time_s', 0) / 60:.0f}분: 도로 {a.max_km} km 안에 새 불 칸 없음 "
                  f"(환경 불 칸 {states or '0'})", flush=True)
            if not a.auto:
                return
            next_s += a.every_min * 60
            continue
        c, d = got
        done.add(c["cell_id"])
        n += 1
        print(f"시뮬레이션 {snap.get('simulation_time_s', 0) / 60:.0f}분: 칸 {c['cell_id']} ({c.get('fire_state')}) — 도로까지 {d:.0f} m", flush=True)
        if not a.dry_run:
            request(cx, a.orch, c, n, a.wait_s)
        next_s = snap.get("simulation_time_s", 0.0) + a.every_min * 60


if __name__ == "__main__":
    main()
