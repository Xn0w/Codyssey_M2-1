"""6단계 커버리지 순회: 한 차량이 구역 안 '정적 통과·아직 안 달림' 링크 위 목표를 차례로 돈다 (각 목표 도착 → 다음 목표, 끝에 거점 복귀).
목표는 coverage.json 의 TEST_TARGET 링크 중 구역 도로 부분집합에 있는 것, 가까운 순(탐욕).
  UGV_GZ_WORLD=tz_a33 python logs/ugv/stage4/sweep.py --rid A-ugv1 --subset logs/ugv/stage5/tiles/road_subset_tz_a33.json --n 12 --track-s 2400
"""
import argparse
import json
import math
import sys
import time

sys.path.insert(0, ".")
from ugv.tools import fleet_test  # noqa: E402
from ugv.roads import RoadNetwork  # noqa: E402
from ugv.approach import node_id_of  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rid", default="A-ugv1")
    ap.add_argument("--subset", required=True)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--track-s", type=float, default=2400)
    a = ap.parse_args()
    net = RoadNetwork()
    sub = set(json.load(open(a.subset))["roads"])
    prof = "adair_ugv" if "ugv" in a.rid else "adair_firetruck"
    cov = json.load(open("logs/ugv/stage5/coverage.json", encoding="utf-8"))["vehicles"][prof]["links"]
    cand = [rid for rid in sub if cov.get(rid, {}).get("status") == "TEST_TARGET" and net.roads[rid].length >= 40]
    run = fleet_test.Run(f"sweep_{a.rid}", a.track_s, rids=[a.rid])
    st = run.c.get(f"/ugv/{a.rid}/state").json()
    from ugv.geo import FRAME
    x, y = FRAME.to_xy(st["position"]["lat"], st["position"]["lon"])
    done, k = [], 0
    end = time.time() + a.track_s * 0.85
    while cand and len(done) < a.n and time.time() < end:
        cand.sort(key=lambda r: math.dist((x, y), net.at(r, net.roads[r].length / 2)[2:4]))
        rid = cand.pop(0)
        p = net.at(rid, net.roads[rid].length / 2)
        k += 1
        key = f"SW{k}-{a.rid}"
        rec = run.go(a.rid, key, node=node_id_of(p))
        if rec["status_code"] != 200:
            done.append({"link": rid, "result": "REJECT", "detail": str(rec.get("response"))[:160]})
            continue
        run.wait([(a.rid, key)], 600, every=2.0)
        t = run.task(a.rid, key)
        done.append({"link": rid, "result": t.get("status"), "error": t.get("error")})
        print(f"[{run.t():7.1f}] {rid} → {t.get('status')} {t.get('error') or ''}", flush=True)
        if t.get("status") != "COMPLETED":
            break                                            # 실패하면 멈춘다 (다음 목표로 덮지 않음)
        x, y = p.x, p.y
    run.log["sweep"] = done
    hk = f"SWH-{a.rid}"
    if run.home(a.rid, hk)["status_code"] == 200:
        run.wait([(a.rid, hk)], 900, every=2.0)
    run.finish()


if __name__ == "__main__":
    main()
