# -*- coding: utf-8 -*-
"""7.1 후보 회전의 전체 계획기 평가 (오프라인): 같은 출발(진입 도로 노드 45 m 앞)·목표(진출 도로 노드 20 m 뒤)로
UGV(adair_ugv) 와 소방차(fire_v2 제원 사본) 를 evaluate → ACCEPT/REJECT·경로가 그 회전을 쓰는지.
실행 (ADAIR_wt_integ): python ../ADAIR/logs/ugv/stage6/eval_turn_reject.py <node> <in_road> <out_road> [...]"""
import asyncio
import dataclasses
import json
import math
import os
import pathlib
import sys
import tempfile

M = pathlib.Path(__file__).resolve().parents[3]
os.environ["UGV_ROAD_SUBSET"] = str(M / "logs/ugv/stage5/tiles_v2/road_subset_all_included.json")
os.environ.setdefault("UGV_ALLOW_NO_FIRE_DATA", "1")
os.environ.setdefault("UGV_LAT_ACCEL", "1.0")
sys.path.insert(0, ".")
import ugv.profiles as P                               # noqa: E402
P.PROFILES["adair_firetruck"] = dataclasses.replace(P.PROFILES["adair_firetruck"], wheelbase_m=4.3, body_length_m=7.67, body_width_m=2.42,
                                                    rear_axle_from_center_m=1.865, mass_kg=12175.0)   # fire_v2 제원 (오프라인 평가 전용 사본)
from ugv.roads import RoadNetwork                      # noqa: E402
import ugv.tests.test_multi_vehicle as tm              # noqa: E402
from ugv.tests.test_multi_vehicle import FLEET_CFG, make_fleet   # noqa: E402
from ugv.geo import FRAME                              # noqa: E402

net = RoadNetwork()
tm.NET = net
res = []
args = sys.argv[1:]
for i in range(0, len(args), 3):
    node, rin, rout = args[i:i + 3]
    a, b = net.roads[rin], net.roads[rout]
    s0 = a.length - 45.0 if a.b == node else 45.0
    s0 = min(max(s0, 1.0), a.length - 1.0)
    p0, p1 = net.at(rin, s0), net.at(rin, s0 + (1.0 if a.b == node else -1.0))
    hdg = math.degrees(math.atan2(p1.x - p0.x, p1.y - p0.y)) % 360
    st = min(20.0, b.length - 1.0) if b.a == node else max(b.length - 20.0, 1.0)
    target = f"RP:{rout}:{st:.1f}"
    lat, lon = FRAME.to_ll(p0.x, p0.y)
    row = {"node": node, "in": rin, "out": rout, "target": target}
    for kind, rid in (("UGV", "A-ugv1"), ("FIRE_v2", "A-fire1")):
        base = next((c for c in FLEET_CFG if c["resource_id"] == rid), None)
        if base is None:
            row[kind] = "fleet 설정 없음"
            continue
        cfg = dict(base, initial={"lat": lat, "lon": lon, "heading_deg": hdg})
        try:
            f, _ = make_fleet(pathlib.Path(tempfile.mkdtemp()), [cfg])
            ev = asyncio.run(f.vehicles[rid].evaluate({"task_id": "T", "decision_id": "T", "target_node": target}))
        except Exception as e:  # noqa: BLE001
            row[kind] = {"verdict": "ERROR", "detail": str(e)[:160]}
            continue
        path = [str(x) for x in (ev.get("path") or [])]
        uses = any(path[k] == rin and path[k + 1] == rout for k in range(len(path) - 1))
        row[kind] = {"verdict": ev.get("verdict"), "reason": ev.get("reason") or ev.get("detail"), "uses_turn": uses,
                     "eta_s": ev.get("eta_sec"), "path_len": len(path), "path_head": path[:8]}
    res.append(row)
    print(json.dumps(row, ensure_ascii=False, default=str)[:600])
(M / "logs/ugv/stage6/turn_reject_eval.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
