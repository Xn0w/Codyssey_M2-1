# -*- coding: utf-8 -*-
"""후속 계획 S4 7.3 남은 경사 조건 후보 (UGV): 종단 전이(마루·골) 통과, 횡경사 회전. 결과 보기 전 기준 (2026-10-13):
  전이: 20 m 창 종단 경사 변화 |Δg| 최대 ≥ 0.04, 길이 ≥ 80 m, 횡경사 ≤ 0.03, 누적 회전 ≤ 20°  → |Δg| 큰 순 3
  횡경사 회전: 누적 회전 ≥ 30°, 최소 곡률 반경 20~100 m, 횡경사 최대 0.02~0.06, 종단 최대 ≤ 0.08 → 횡경사 큰 순 3
지면 = tiles_v2 높이맵 (Gazebo 충돌면). road_candidates.road_metrics 재사용 + 경사 변화 계산.
실행 (ADAIR_wt_vehicle): python ../ADAIR/logs/ugv/stage6/find_slope2.py"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")
from ugv.roads import RoadNetwork                       # noqa: E402
from ugv.tools import build_terrain_tiles as BT         # noqa: E402
from ugv.tools import road_candidates as RC             # noqa: E402

M = Path(__file__).resolve().parents[3]
T = M / "logs/ugv/stage5/tiles_v2"
S = RC.Surf(T)
net = RoadNetwork()
roads = set(json.loads((T / "road_subset_all_included.json").read_text(encoding="utf-8"))["roads"]) & set(net.roads)
junctions = BT.junction_nodes(net, list(roads))
rows = []
for rid in sorted(roads):
    r = net.roads[rid]
    if r.length < 60:
        continue
    m = RC.road_metrics(net, S, rid, junctions)
    if not m:
        continue
    s = np.arange(0.0, r.length + 1e-9, 2.0)
    z = np.array([S.z(p.x, p.y) for p in (net.at(rid, v) for v in s)])
    w = 10
    g = (z[w:] - z[:-w]) / (s[w:] - s[:-w]) if len(z) > 2 * w else np.array([0.0])
    dg = np.abs(g[w:] - g[:-w]) if len(g) > w else np.array([0.0])
    m["grade_change_max"] = round(float(dg.max()), 4)
    m["grade_change_at_s"] = round(float(s[int(dg.argmax()) + w]), 1) if len(dg) else None
    rows.append(m)
trans = [m for m in rows if m["grade_change_max"] >= 0.04 and m["len_m"] >= 80 and m["cross_max"] <= 0.03 and m["turn_total_deg"] <= 20]
trans.sort(key=lambda m: -m["grade_change_max"])
xturn = [m for m in rows if m["turn_total_deg"] >= 30 and m["min_radius_m"] and 20 <= m["min_radius_m"] <= 100
         and 0.02 <= m["cross_max"] <= 0.06 and m["grade_max"] <= 0.08]
xturn.sort(key=lambda m: -m["cross_max"])
out = {"criteria": __doc__, "roads_scanned": len(rows), "transition": trans[:3], "cross_slope_turn": xturn[:3],
       "transition_count": len(trans), "cross_slope_turn_count": len(xturn)}
(M / "logs/ugv/stage6/slope2_candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("검사", len(rows), "전이", len(trans), "횡경사회전", len(xturn))
for k in ("transition", "cross_slope_turn"):
    for m in out[k]:
        print(k, m["road"], m["len_m"], "Δg", m["grade_change_max"], "@", m["grade_change_at_s"], "횡", m["cross_max"], "회전", m["turn_total_deg"], "R", m["min_radius_m"], m["tiles"])
