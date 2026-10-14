# -*- coding: utf-8 -*-
"""간헐 실패 진단 사후 분석 (flaky_diag v3 의 run*.jsonl → post.json). 실행 중 계산을 줄이려고 무거운 지도 계산은 여기서 한다.
실행 (ADAIR_wt_integ 에서): python ../ADAIR/logs/ugv/stage6/flaky_post.py <diag_dir>

회차마다:
 - 고장 차 A 차체 영역 (정지 위치·heading·프로필 길이/폭, 원점 = 뒤축 중심 가정 → 근사) 을 0.25 m 격자점으로 나눠
   도로 띠(중심선에서 drive_graph.est_half_width 이내 — 서버 계획기와 같은 반폭 추정)에 드는 도로 = '차체 점유 도로 (반폭 추정 기준)'.
   차체 중심·모서리 snap = '가장 가까운 도로 후보' 로 따로 표시 (점유 증거 아님).
 - A-ugv2 계획(PLAN/APPROACH) 마다 계획선을 따라 차체 반폭(프로필 폭/2) 만큼 넓힌 띠가 A 차체와 처음 겹치는 경로상 거리 = 충돌 예측 지점.
 - BLOCKED_CALL 순간의 A-ugv2 경로상 위치, 그 뒤 APPROACH 의 회피 대상(extra_avoid) 도로, 재계획 경로의 재충돌 지점을 연결.
한계: 도로 폭은 차로 수 기반 추정, 회전 연결부는 도로 띠 합집합으로만 본다. 원점 가정은 근사.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, ".")
from ugv.drive_graph import est_half_width                       # noqa: E402
from ugv.tests import test_orchestrator_closed_loop as T          # noqa: E402

NET = T.NET
HW = {rid: est_half_width(r) for rid, r in NET.roads.items()}


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def road_pts(r):
    return r.xy


def body_points(p, prof, step=0.25):
    hd = math.radians(p["heading"])
    fx, fy = math.sin(hd), math.cos(hd)
    rx, ry = fy, -fx
    cx, cy = p["x"] + fx * prof["rear_axle_from_center_m"], p["y"] + fy * prof["rear_axle_from_center_m"]
    hl, hw = prof["body_length_m"] / 2, prof["body_width_m"] / 2
    out = []
    a = -hl
    while a <= hl + 1e-9:
        b = -hw
        while b <= hw + 1e-9:
            out.append((cx + fx * a + rx * b, cy + fy * a + ry * b))
            b += step
        a += step
    corners = {n: (cx + fx * a2 + rx * b2, cy + fy * a2 + ry * b2) for n, (a2, b2) in
               {"center": (0, 0), "fl": (hl, -hw), "fr": (hl, hw), "rl": (-hl, -hw), "rr": (-hl, hw)}.items()}
    return out, corners, (cx, cy, max(hl, hw) + 1.0)


def occupied_roads(points, center):
    cx, cy, rad = center
    occ = {}
    for rid, r in NET.roads.items():
        P = road_pts(r)
        if not P or min(math.hypot(x - cx, y - cy) for x, y in P[:: max(1, len(P) // 20)] + [P[-1]]) > rad + 300:
            continue
        hw = HW[rid]
        n = 0
        for (px, py) in points:
            if any(seg_dist(px, py, *P[i], *P[i + 1]) <= hw for i in range(len(P) - 1)):
                n += 1
        if n:
            occ[rid] = round(n / len(points), 3)
    return occ


def first_overlap(route_pts, body_pts, half_w):
    """계획선 띠(half_w)가 A 차체 격자점(0.25 m)에 처음 닿는 '선분 구간' [시작 s, 끝 s] (정확한 교차 지점이 아님 — 구간·격자 근사)."""
    s = 0.0
    for i in range(len(route_pts) - 1):
        (ax, ay), (bx, by) = route_pts[i], route_pts[i + 1]
        seg = math.hypot(bx - ax, by - ay)
        if any(seg_dist(px, py, ax, ay, bx, by) <= half_w for px, py in body_pts):
            return {"segment_s": [round(s, 1), round(s + seg, 1)], "segment_start_xy": [round(ax, 1), round(ay, 1)],
                    "basis": "선분 구간·차체 0.25 m 격자·추정 반폭 근사 (정확한 충돌 지점 아님)"}
        s += seg
    return None


def snap_road(p):
    if not p:
        return None
    q = NET.snap(p["x"], p["y"])
    return None if q is None else q.road_id


def main():
    d = Path(sys.argv[1])
    out = []
    for f in sorted(d.glob("run*.jsonl")):
        recs, bad_lines = [], []
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):   # 원본 파일은 그대로 둔다
            if not line.strip():
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                bad_lines.append(n)                     # 잘린 마지막 줄 등 — 표시하고 나머지는 분석
        res = next((r for r in recs if r["kind"] == "RESULT"), None)
        stop = next((r for r in recs if r["kind"] == "A_STOP"), None)
        row = {"run": f.stem, "class": (res or {}).get("class", "RESULT 없음 (부분 기록)"), "b_error": (res or {}).get("b_error"),
               "result_complete": res is not None, "invalid_lines": bad_lines, "records": len(recs)}
        if stop is None:
            out.append(row)
            continue
        prof = stop["profile"]
        bp, corners, center = body_points(stop["pose"], prof)
        row["a_occupied_roads_halfwidth_est"] = occupied_roads(bp, center)
        row["a_nearest_road_candidates"] = {n: (lambda q: None if q is None else q.road_id)(NET.snap(x, y)) for n, (x, y) in corners.items()}
        bw = prof["body_width_m"] / 2
        plans = [r for r in recs if r["kind"] in ("PLAN", "APPROACH") and r.get("vehicle") == "A-ugv2" and r.get("pts")]
        row["b_plans"] = [{"kind": r["kind"], "sim_t": r.get("sim_t"), "extra_avoid": r.get("extra_avoid"), "status": r.get("status"),
                           "roads": r.get("road_ids"), "first_overlap_with_A": first_overlap(r["pts"], bp, bw)} for r in plans]
        # 실제 전송 경유점 (계획선과 다를 수 있음) 기준 겹침 — 경유점이 (x, y, …) 형식일 때
        sends = [r for r in recs if r["kind"] == "FOLLOW_SEND" and r.get("vehicle") == "A-ugv2"]
        row["b_sent"] = []
        for r in sends:
            xy = [it[:2] for it in r.get("items", []) if isinstance(it, list) and len(it) >= 2 and all(isinstance(v, (int, float)) for v in it[:2])]
            row["b_sent"].append({"sim_t": r.get("sim_t"), "seq_before": r.get("seq_before"), "n_items": len(r.get("items", [])),
                                  "first_overlap_with_A": first_overlap(xy, bp, bw) if len(xy) >= 2 else "경유점 좌표 형식 아님"})
        # 코드가 회피 대상으로 고르는 도로 = 상대(A) 텔레메트리 원점 snap 하나 (vehicle.blocked_by_vehicle) — 점유 도로 전체와 비교
        row["blocked_calls"] = [{"sim_t": r["sim_t"], "b_s": r.get("self_s"), "b_pose": r.get("self_pose"), "prior": r.get("prior_blocked"),
                                 "code_avoid_road_origin_snap": snap_road(r.get("other_pose"))}
                                for r in recs if r["kind"] == "BLOCKED_CALL"]
        row["first_traffic_events"] = [{"sim_t": r["e"].get("sim_time_s"), "event": r["e"].get("event"), "why": r["e"].get("why"), "other": r["e"].get("other")}
                                       for r in recs if r["kind"] == "EVENT" and r.get("vehicle") == "A-ugv2"
                                       and str(r["e"].get("event", "")).startswith(("TRAFFIC", "YIELD", "REPLANNED", "BLOCK"))][:12]
        tm = next((r for r in recs if r["kind"] == "TIMING"), {})
        row["timing"] = {k: v for k, v in tm.items() if k not in ("kind", "wall")}
        ft = next((r for r in recs if r["kind"] == "FAULT_TIMELINE"), {})
        row["fault_timeline"] = {"obs_to_request_s": None if not ft.get("cond_observed_wall") else round(ft["request_wall"] - ft["cond_observed_wall"], 3),
                                 "request_to_response_s": None if not ft.get("request_wall") else round(ft["response_wall"] - ft["request_wall"], 3),
                                 "s_at_request": ft.get("s_at_request")}
        out.append(row)
        print(f.stem, row["class"], "점유(추정)", row["a_occupied_roads_halfwidth_est"], "최근접", set(row["a_nearest_road_candidates"].values()),
              "B계획", [(p["kind"], p["extra_avoid"], (p["first_overlap_with_A"] or {}).get("segment_s")) for p in row["b_plans"]])
    summary = {"run_files": len(out), "result_complete": sum(1 for r in out if r.get("result_complete")),
               "with_invalid_lines": sum(1 for r in out if r.get("invalid_lines"))}
    print("POST_SUMMARY", json.dumps(summary, ensure_ascii=False))
    (d / "post.json").write_text(json.dumps({"summary": summary, "runs": out}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
