# -*- coding: utf-8 -*-
"""경사 시험 사례 (2026-10-13 후속 계획 S4 7.3 / 차량 개조 계획 T6). 실행: python logs/ugv/stage6/make_slope_cases.py  (계획 코드 = ADAIR_wt_fix)

후보 = road_candidates (tiles_v2, 결과 보기 전 기준: 길이 ≥ 150 m·횡경사 ≤ 2 %·방향 변화 ≤ 15°·평균 등급 띠 안에서 가장 일정한 것).
  3~4 %: 682503113 (153 m, 평균 3.78 %, 표준편차 1.1 %, 최대 5.2 %) — 682502940 (337 m, 평균 3.84 %) 은 표준편차 4.8 %·최대 10.1 % 로
         '일정한 3~4 %' 가 아니어서 대표에서 뺀다 (기록).
  5~6 %: 683400547 (176 m, 평균 5.48 %, 표준편차 0.04 %).
  7~8 %: tiles_v2 에 없음.
사례 = 도로마다 오르막·내리막: 출발 = 도로 끝에서 10 m 안쪽 (차체 중심, 도로 방향), 목표 = 반대쪽 끝 10 m 안쪽 (RP:road:s).
  오프라인 계획(같은 도로 부분집합)으로 ACCEPT 이고 경로가 그 도로를 지나는지 확인. 생성 높이 = 타일 지면 + 0.45 m.
"""
import asyncio
import json
import math
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]          # .../GitHub
M = ROOT / "ADAIR"
WT = ROOT / "ADAIR_wt_fix"
ST = M / "logs/ugv/stage5"
OUT = M / "logs/ugv/stage6/slope"
SUB = ST / "tiles_v2/road_subset_all_included.json"
os.environ["UGV_ROAD_SUBSET"] = str(SUB)
os.environ.setdefault("UGV_ALLOW_NO_FIRE_DATA", "1")
os.environ.setdefault("UGV_LAT_ACCEL", "1.0")
sys.path.insert(0, str(WT))

from ugv.roads import RoadNetwork                      # noqa: E402
import ugv.tests.test_multi_vehicle as tm              # noqa: E402
from ugv.tests.test_multi_vehicle import FLEET_CFG, make_fleet   # noqa: E402
from ugv.geo import FRAME                              # noqa: E402
from ugv.tools.terrain_compare import Surf             # noqa: E402

ROADS = {"682503113": ("3-4%", "wj494846_1237_1921"), "683400547": ("5-6%", "wj495731_0574_0583")}
END_M = 10.0
TARGET_END_M = (10.0, 25.0, 40.0)   # 목표가 거절되면 끝에서 더 안쪽 (오르막 끝 목표는 회차·복귀 경로가 없을 수 있음)
PX = {"A-ugv1": (1, 14541), "B-ugv1": (3, 14543)}


def main():
    global OUT, ROADS
    # 선택: python make_slope_cases.py <출력 폴더> <도로>:<구분>:<월드> ... (2026-10-13 7.3 남은 조건 — 종단 전이·횡경사 회전). 인자 없으면 기존 경사 사례
    if len(sys.argv) > 2:
        OUT = M / "logs/ugv/stage6" / sys.argv[1]
        ROADS = {x.split(":")[0]: (x.split(":")[1], x.split(":")[2]) for x in sys.argv[2:]}
    OUT.mkdir(parents=True, exist_ok=True)
    net = RoadNetwork()
    tm.NET = net
    CFG = {r: next(c for c in FLEET_CFG if c["resource_id"] == r) for r in PX}
    S = Surf(ST / "tiles_v2")
    cases = []
    for rid_road, (band, world) in ROADS.items():
        r = net.roads[rid_road]
        pa, pb = net.at(rid_road, END_M), net.at(rid_road, r.length - END_M)
        za, zb = S.z(pa.x, pa.y), S.z(pb.x, pb.y)
        for direction, end_m in [(d, e) for d in ("up", "down") for e in TARGET_END_M]:
            if any(c["road"] == rid_road and c["direction"] == direction for c in cases):
                continue
            # 오르막: 낮은 끝 → 높은 끝. 목표가 거절(돌아올 경로 없음 등)되면 목표를 도로 끝에서 더 안쪽으로 (TARGET_END_M 순서)
            start_at_a = (za < zb) == (direction == "up")
            s0, s1 = (END_M, r.length - end_m) if start_at_a else (r.length - END_M, end_m)
            p0 = net.at(rid_road, s0)
            p1 = net.at(rid_road, s0 + (1.0 if start_at_a else -1.0))
            hdg = math.degrees(math.atan2(p1.x - p0.x, p1.y - p0.y)) % 360
            target = f"RP:{rid_road}:{s1:.1f}"
            lat, lon = FRAME.to_ll(p0.x, p0.y)
            ok, ev, path, used = False, {"verdict": "NONE"}, [], None
            for vid in PX:
                cfg = dict(CFG[vid], initial={"lat": lat, "lon": lon, "heading_deg": hdg})
                try:
                    f, _ = make_fleet(pathlib.Path(tempfile.mkdtemp()), [cfg])
                    ev = asyncio.run(f.vehicles[vid].evaluate({"task_id": "S", "decision_id": "S", "target_node": target}))
                except Exception as e:  # noqa: BLE001
                    ev = {"verdict": "ERROR", "detail": str(e)[:120]}
                    continue
                path = [str(x) for x in (ev.get("path") or [])]
                if ev["verdict"] == "ACCEPT":
                    ok, used = rid_road in path, (vid, cfg)
                    break
            cid = f"s{rid_road[-4:]}_{direction}"
            if not ok:
                print("제외", cid, ev.get("verdict"), path[:6], ev.get("detail") or ev.get("reason"))
                continue
            vid, cfg = used
            z = S.z(p0.x, p0.y) - 172.1 + 0.45
            yaw = math.radians(90.0 - hdg)
            inst, port = PX[vid]
            (OUT / f"{cid}_spawn.txt").write_text(f"{inst} adair_ugv {p0.x:.2f},{p0.y:.2f},{z:.3f},{yaw:.4f} {vid}\n", encoding="utf-8")
            (OUT / f"{cid}_fleet.json").write_text(json.dumps([dict({k: v for k, v in cfg.items() if k != "driver"}, driver="px4",
                                                                    px4={"address": f"udpin://0.0.0.0:{port}", "instance": inst,
                                                                         "gz_world": "kangwon_flat", "gz_model": f"adair_ugv_{inst}"})],
                                                              ensure_ascii=False, indent=1), encoding="utf-8")
            case = {"id": cid, "road": rid_road, "band": band, "direction": direction, "world": world, "rid": vid, "instance": inst,
                    "target": target, "start_xy": [round(p0.x, 2), round(p0.y, 2)], "z_start": round(S.z(p0.x, p0.y), 2),
                    "z_end": round(S.z(net.at(rid_road, s1).x, net.at(rid_road, s1).y), 2), "len_m": round(abs(s1 - s0), 1),
                    "eta_s": ev.get("eta_sec"), "path": path}
            cases.append(case)
            print("사례", cid, band, direction, "고도", case["z_start"], "→", case["z_end"], "eta", ev.get("eta_sec"), vid)
    (OUT / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    print("사례", len(cases))


if __name__ == "__main__":
    main()
