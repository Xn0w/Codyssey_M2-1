# -*- coding: utf-8 -*-
"""후속 계획 S4 7.1: UGV 는 통과하고 소방차(fire_v2 제원)는 계획상 거절되는 회전 후보 (오프라인, Gazebo 없음).
실행 (ADAIR_wt_integ 에서): python ../ADAIR/logs/ugv/stage6/find_turn_reject.py
- UGV 주행 그래프(profiles adair_ugv) vs 소방차 그래프(현재 adair_firetruck 프로필을 fire_v2 SDF 제원으로 바꾼 사본 — 축간 4.3, 차체 7.67×2.42,
  뒤축↔차체 중심 1.865, 질량 12,175. 조향 35° 그대로). 회전 연결(상태 → 다음 상태)이 UGV 에만 있는 것 = 후보.
- tiles_v2 월드가 덮는 도로(road_subset_all_included.json)만. 결과 = 거절 사유(blocked_turns)·회전각·노드 위치.
추정 도로 폭 기반 계획 판정이며, 실제 차로·건물 충돌 검증이 아니다."""
import dataclasses
import json
import os
import sys
from pathlib import Path

M = Path(__file__).resolve().parents[3]
os.environ["UGV_ROAD_SUBSET"] = str(M / "logs/ugv/stage5/tiles_v2/road_subset_all_included.json")
sys.path.insert(0, ".")
from ugv.profiles import PROFILES                      # noqa: E402
from ugv.roads import RoadNetwork                      # noqa: E402
from ugv.drive_graph import DriveGraph                 # noqa: E402

net = RoadNetwork()
ugv = PROFILES["adair_ugv"]
fire = dataclasses.replace(PROFILES["adair_firetruck"], name="adair_firetruck_fire_v2", wheelbase_m=4.3, body_length_m=7.67,
                           body_width_m=2.42, rear_axle_from_center_m=1.865, mass_kg=12175.0)
gu, gf = DriveGraph(net, ugv), DriveGraph(net, fire)
eu = {(s, t.to) for s, ts in gu.turns.items() for t in ts}
ef = {(s, t.to) for s, ts in gf.turns.items() for t in ts}
only = sorted(eu - ef)
why = {}
for b in gf.blocked_turns:
    k = (tuple(b.get("from")) if isinstance(b.get("from"), list) else b.get("from"), tuple(b.get("to")) if isinstance(b.get("to"), list) else b.get("to"))
    why[str(k)] = b
out = []
for s, t in only:
    node = s[1]
    nd = net.nodes.get(node) if hasattr(net, "nodes") else None
    rec = {"from_state": list(s), "to_state": list(t), "node": node,
           "node_xy": None if nd is None else [round(nd[0], 1), round(nd[1], 1)] if isinstance(nd, (list, tuple)) else str(nd),
           "fire_sharp_roads": [r for r in (s[0], t[0]) if r in gf.sharp_roads], "ugv_sharp_roads": [r for r in (s[0], t[0]) if r in gu.sharp_roads]}
    b = next((x for x in gf.blocked_turns if str(x.get("node")) == str(node) and str(s[0]) in json.dumps(x) and str(t[0]) in json.dumps(x)), None)
    rec["fire_block_reason"] = b
    out.append(rec)
summary = {"ugv_turns": len(eu), "fire_v2_turns": len(ef), "ugv_only": len(only), "fire_sharp_roads": len(gf.sharp_roads), "ugv_sharp_roads": len(gu.sharp_roads),
           "fire_profile": {k: getattr(fire, k) for k in ("wheelbase_m", "steer_max_deg", "body_length_m", "body_width_m", "rear_axle_from_center_m")}}
(M / "logs/ugv/stage6/turn_reject_candidates.json").write_text(json.dumps({"summary": summary, "candidates": out}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
for r in out[:15]:
    print(r["node"], r["from_state"], "→", r["to_state"], "급커브(소방차)", r["fire_sharp_roads"], "사유", json.dumps(r["fire_block_reason"], ensure_ascii=False, default=str)[:160] if r["fire_block_reason"] else None)
