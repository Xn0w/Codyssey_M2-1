# -*- coding: utf-8 -*-
"""커버리지 판정 (ugv/tools/coverage_judge.py) — 2026-10-11 검토 재현 조건: 6 m 도로 정지 표본 하나로 통과, 중간 기록 누락,
분석 누락을 정상으로, 이탈 사건 처음 10개만 보고 실패 도로 찾기, 여러 링크에 걸친 이탈을 시작 위치 링크로만."""

import math

from ugv.profiles import get
from ugv.tests.test_multi_vehicle import NET
from ugv.tools import coverage_judge as CJ

P = get("adair_ugv")
G = NET.graph_for(P)


def _rows(rid, s_list, t0=0.0, dt=0.2, lateral=0.0):
    out = []
    for k, s in enumerate(s_list):
        p = NET.at(rid, s)
        q = NET.at(rid, min(s + 1.0, NET.roads[rid].length))
        hd = math.atan2(q.y - p.y, q.x - p.x) if (q.x, q.y) != (p.x, p.y) else 0.0
        nx, ny = -math.sin(hd), math.cos(hd)
        out.append({"sim_t": t0 + k * dt, "x": p.x + nx * lateral, "y": p.y + ny * lateral, "yaw": hd, "roll": 0.0, "pitch": 0.0})
    return out


def _clean(rid):
    """도로 가운데 차체가 도로 안인 표본인지 (짧은 도로 끝은 교차로라 이탈 판정이 다를 수 있다 — 가운데만 본다)."""
    return CJ.body_excess(G, P, _rows(rid, [NET.roads[rid].length / 2])[0]) <= 0


def test_single_standstill_sample_on_short_road_is_not_driven():
    rid = next(r for r, x in NET.roads.items() if 5.0 <= x.length <= 8.0 and _clean(r))
    obs, _ = CJ.observations(NET, G, P, _rows(rid, [NET.roads[rid].length / 2] * 20), True, "t")
    assert rid not in obs or obs[rid]["cover"] < CJ.COVER_MIN
    assert CJ.judge([o for k, o in obs.items() if k == rid])[0] in (None, "INCOMPLETE")


def test_gap_in_middle_of_track_is_not_covered():
    rid = next(r for r, x in NET.roads.items() if 150 <= x.length <= 300 and _clean(r))
    L = NET.roads[rid].length
    s = [i * 1.0 for i in range(int(L) + 1)]
    full, *_ = CJ.scan(NET, G, P, _rows(rid, s))
    assert full.get(rid, 0) >= CJ.COVER_MIN
    rows = _rows(rid, s)                                     # 표본 간격 1 m → 번호 ≈ s
    n = len(rows)
    cut = rows[:int(n * 0.3)] + rows[int(n * 0.5):]           # 30~50 % 구간 기록이 사라짐 (시각은 그대로 이어 붙임)
    for k, r in enumerate(cut):
        r["sim_t"] = k * 0.2
    full2, *_ = CJ.scan(NET, G, P, cut)
    assert full2.get(rid, 0) < CJ.COVER_MIN


def test_incomplete_record_is_not_pass_but_failure_still_counts():
    rid = next(r for r, x in NET.roads.items() if 150 <= x.length <= 300 and _clean(r))
    s = [i * 1.0 for i in range(int(NET.roads[rid].length) + 1)]
    obs, _ = CJ.observations(NET, G, P, _rows(rid, s), False, "no_json")
    assert CJ.judge([obs[rid]])[0] == "INCOMPLETE"
    obs_ok, _ = CJ.observations(NET, G, P, _rows(rid, s), True, "ok")
    assert CJ.judge([obs[rid], obs_ok[rid]])[0] == "DRIVEN_PASS"


def test_offroad_after_tenth_event_and_across_links_marks_every_link():
    rids = [r for r, x in NET.roads.items() if 120 <= x.length <= 300 and _clean(r)][:3]
    rows, t = [], 0.0
    for rid in rids:
        L = NET.roads[rid].length
        for k in range(12):                                  # 도로마다 이탈 사건 12번 (짧은 바깥 이탈 ↔ 복귀)
            base = L * (k + 0.5) / 13
            rows += _rows(rid, [base], t0=t, lateral=0.0); t += 0.6
            rows += _rows(rid, [base + 1.0], t0=t, lateral=7.0); t += 0.6
    obs, meta = CJ.observations(NET, G, P, rows, True, "t")
    assert meta["offroad_samples"] >= 30
    for rid in rids:
        assert obs[rid]["offroad_samples"] >= 1 and CJ.judge([obs[rid]])[0] == "DRIVEN_FAIL"
