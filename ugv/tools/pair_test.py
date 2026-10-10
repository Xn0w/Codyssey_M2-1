# -*- coding: utf-8 -*-
"""ugv/tools/pair_test.py — 두 차량이 같은 교차로·같은 좁은 도로로 동시에 들어오는 Gazebo 시험 (모의 시험과 같은 배치).

    python -m ugv.tools.pair_test make junction     # 차량 설정 JSON·스폰 자세 파일을 logs/ugv/ 에 만든다
    (WSL) bash ugv/tools/wsl_start_fleet.sh logs/ugv/pair_junction_spawn.txt
    UGV_VEHICLES_JSON=logs/ugv/pair_junction_fleet.json UGV_DRIVER=px4 uvicorn ugv.server:app --port 8100
    python -m ugv.tools.pair_test run junction

junction: 다른 거점 차량(A-ugv1·B-fire1)이 교차로 494928 로 각자 다른 도로에서 110 m 떨어져 출발 → 같은 도로 682501929 로 합류
          (X 목적지 170 m, Y 60 m). 기대: 늦게 오는 차가 교차로 앞에서 기다린다(YIELD), 차체 겹침 0, 간격 > 1 m.
block:    교차로 배치에서 목적지를 바꿈 — A-ugv1 이 합류 도로 60 m 에 서고 B-fire1 은 그 너머 170 m 로. 기대: B-fire1 이 막힘 처리
          (우회 경로로 다시 계획해 도착, 또는 우회가 없으면 기다리지 않고 BLOCKED_BY_VEHICLE 실패 보고 후 정지), 겹침 0, 재계획 1회 이하.
head_on:  A-ugv1·A-fire1 이 공유 도로 683400826 양 끝에서 70 m 떨어져 출발, 서로 반대 방향으로 그 도로를 지나야 함.
          기대: UGV 가 그 도로에 들어가기 전에 기다린다(YIELD HEAD_ON, 소방차 우선), 겹침 0.
배치는 ugv/tests/test_multi_vehicle.py 의 JUNCTION·HEAD_ON (진행 방향·복귀 조건으로 두 차 모두 계획되는 곳, 2026-10-10).
판정은 fleet_test.analyze (Gazebo 자세만, 차종 치수 vs 추정 도로 띠, 차량 쌍 겹침).
"""

import argparse
import json
import math
import time
from pathlib import Path

from ugv.approach import node_id_of
from ugv.geo import FRAME, bearing_deg
from ugv.roads import RoadNetwork
from ugv.tools import fleet_test
from ugv.tools.drive_test import LOG_DIR
from ugv.tools.spawn_pose import Z

JUNCTION = ("494928", "682501307", "682501539", "682501929")        # 노드, X 진입, Y 진입, 합류 도로
HEAD_ON = ("683400826", "683400838", "683400828", "683401696", "683400719")   # 공유 도로, X 진입, Y 진입, X 진출, Y 진출
CFG = {c["resource_id"]: c for c in fleet_test.FLEET}
TURN_SC = {"turn_naerin_ugv": ("682502376", "494861", "682502932", "A-ugv1"),      # 국도 31 내린천로 굽음 (38.0084, 128.2415)
           "turn_naerin_fire": ("682502376", "494861", "682502932", "A-fire1"),
           "turn_deoksan_ugv": ("682501903", "495178", "682600487", "A-ugv1"),     # 덕산로 교차로 직진 (38.0886, 128.1834)
           "turn_deoksan_fire": ("682501903", "495178", "682600487", "A-fire1"),
           "turn_deoksan101_ugv": ("682501903", "495178", "682501906", "A-ugv1")}  # 같은 교차로 101° 회전


def _pose(net, rid, node, dist):
    r = net.roads[rid]
    s = r.length - dist if node == r.b else dist
    p = net.at(rid, s)
    q = net.at(rid, s + 1 if node == r.b else s - 1)
    return p, q


def layout(sc):
    """[(차량 ID, 진입 도로, 진입 노드, 출발 거리 m, 목표 도로, 목표 s m)]"""
    net = RoadNetwork()
    if sc == "junction":
        n, r1, r2, r3 = JUNCTION
        q3 = net.roads[r3]
        s = lambda d: d if q3.a == n else q3.length - d
        return net, [("A-ugv1", r1, n, 110, r3, s(170.0)), ("B-fire1", r2, n, 110, r3, s(60.0))]
    if sc in TURN_SC:
        # 한 대가 교차로 회전 하나만 지난다 (B 거점 → A 지역 경로에서 이음매 때문에 막혔던 회전, 2026-10-10 지도 대조: 일반 2차로)
        r1, node, r2, rid = TURN_SC[sc]
        q2 = net.roads[r2]
        return net, [(rid, r1, node, 150, r2, 80.0 if q2.a == node else q2.length - 80.0)]
    if sc == "block":
        # 교차로 배치에서 목적지를 바꾼다: 먼저 합류하는 A-ugv1 이 합류 도로 60 m 에 서고(임무 끝 → 스스로 움직이지 않음),
        # 뒤따르는 B-fire1 은 그 너머 170 m 로 가야 한다 → 막힘 처리 (우회 재계획 또는 BLOCKED_BY_VEHICLE 실패 보고)
        n, r1, r2, r3 = JUNCTION
        q3 = net.roads[r3]
        s = lambda d: d if q3.a == n else q3.length - d
        return net, [("A-ugv1", r1, n, 110, r3, s(60.0)), ("B-fire1", r2, n, 125, r3, s(170.0))]
    rid, ra, rb, rc, rd = HEAD_ON
    r, qc, qd = net.roads[rid], net.roads[rc], net.roads[rd]
    return net, [("A-ugv1", ra, r.a, 70, rc, 60.0 if qc.a == r.b else qc.length - 60.0),
                 ("A-fire1", rb, r.b, 70, rd, 60.0 if qd.a == r.a else qd.length - 60.0)]


def _a_route(net):
    """A-ugv1 이 거점 출입 지점에서 표준 목표(출입 지점 −900, −700)로 가는 계획 (sim 계획기, 시험 배치 계산용)."""
    import pathlib, tempfile, asyncio
    from ugv.tests.test_multi_vehicle import make_fleet
    cfg = {**CFG["A-ugv1"], "driver": "sim"}
    f, _ = make_fleet(pathlib.Path(tempfile.mkdtemp()), [cfg])
    A = f.vehicles["A-ugv1"]
    tgt = FRAME.to_ll(A.access.x - 900, A.access.y - 700)
    asyncio.run(A.execute({"task_id": "P", "decision_id": "D", "target": {"lat": tgt[0], "lon": tgt[1]}}))
    return A, tgt


def _pose_on(net, rid, s, toward):
    r = net.roads[rid]
    p = net.at(rid, s)
    q = net.at(rid, s + (1.0 if toward == r.b else -1.0))
    return p, q


SPECIAL = ("static_ahead", "linkloss_approach")


TEST_ROAD = "682501747"     # A 지역 직선 국도 1,277 m (양방향, UGV·소방차 주행 묶음, 급커브 아님) — 시험용 배치


def make_special(sc):
    """시험용 배치 (운영 거점·기본 배치와 별개, 시작 자세만): TEST_ROAD 위 a→b 방향.
    static_ahead: A-ugv1 s=100 출발 → 목적지 s=900, 그 사이 s=400 에 고장 차(B-fire1). 정지거리 밖에서 빠르게 다가가 서야 한다.
    linkloss_approach: A-ugv1 s=250(앞), A-fire1 s=130(뒤), 둘 다 목적지 s=1150. 둘 다 움직이면 앞차 링크를 끊는다."""
    net = RoadNetwork()
    rid = TEST_ROAD
    r = net.roads[rid]
    toward = r.b
    ll = lambda s_: FRAME.to_ll(net.at(rid, s_).x, net.at(rid, s_).y)
    if sc == "static_ahead":
        poses = {"A-ugv1": _pose_on(net, rid, 100.0, toward), "B-fire1": _pose_on(net, rid, 400.0, toward)}
        plan = {"moving": {"A-ugv1": ll(900.0)}, "faulted": ["B-fire1"], "road": rid}
    else:
        poses = {"A-ugv1": _pose_on(net, rid, 250.0, toward), "A-fire1": _pose_on(net, rid, 130.0, toward)}
        plan = {"moving": {"A-ugv1": ll(1150.0), "A-fire1": ll(1150.0)}, "cut": "A-ugv1", "road": rid}
    fleet, spawn = [], []
    for rid_, (p, q) in poses.items():
        lat, lon = FRAME.to_ll(p.x, p.y)
        fleet.append({**CFG[rid_], "initial": {"lat": lat, "lon": lon, "heading_deg": round(bearing_deg(q.x - p.x, q.y - p.y), 2)}})
        yaw = math.atan2(q.y - p.y, q.x - p.x)
        spawn.append(f'{CFG[rid_]["px4"]["instance"]} {CFG[rid_]["profile"]} {p.x:.2f},{p.y:.2f},{Z[CFG[rid_]["profile"]]},{yaw:.4f} {rid_}')
    fp, sp, pp = LOG_DIR / f"pair_{sc}_fleet.json", LOG_DIR / f"pair_{sc}_spawn.txt", LOG_DIR / f"pair_{sc}_plan.json"
    fp.write_text(json.dumps(fleet, ensure_ascii=False, indent=1), encoding="utf-8")
    sp.write_text("\n".join(spawn) + "\n", encoding="utf-8")
    pp.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(fp, sp, *spawn, sep="\n")


def wait_stopped(r, rids, track_s, extra=None):
    """임무가 끝나도(막힘 실패 등) 차가 대기 지점까지 가서 설 때까지 본다 — 서기 전에 기록을 끝내면 정지 간격을 못 잰다."""
    t_end = r.t0 + track_s
    while time.time() < t_end:
        p = r.poll()
        if extra:
            extra(p)
        mv = [rid for rid in rids if p["vehicles"][rid]["mission"] in ("DRIVING", "STOPPING", "EVADING")
              or (p["vehicles"][rid]["speed"] or 0) > 0.1]
        if not mv:
            return True
        print(f"[{r.t():6.1f}] 정지 기다림 {mv}", flush=True)
        time.sleep(1.0)
    return False


def run_special(sc, track_s, after_s, cut_after_s=15.0):
    plan = json.loads((LOG_DIR / f"pair_{sc}_plan.json").read_text(encoding="utf-8"))
    rids = list(plan["moving"]) + plan.get("faulted", [])
    r = fleet_test.Run(f"pair_{sc}", track_s, rids=rids)
    r.log["special_plan"] = plan
    for rid in plan.get("faulted", []):                 # 출발 전 고장 (스스로 움직이지 않는 차)
        r.log.setdefault("faults", {})[rid] = r.c.post(f"/ugv/{rid}/_test/fault",
                                                       json={"code": "VEHICLE_FAULT", "detail": "시험: 도로 위 고장 정지"}).json()
    keys = []
    for i, (rid, (lat, lon)) in enumerate(plan["moving"].items()):
        key = f"P-{sc[:2].upper()}{i}-{rid}"
        rec = r.go(rid, key, lat, lon)
        if rec["status_code"] == 200:
            keys.append((rid, key))
    st = {"cut": None}

    def maybe_cut(p):
        if plan.get("cut") and st["cut"] is None and r.t() > cut_after_s:
            v = p["vehicles"][plan["cut"]]
            if (v["speed"] or 0) > 5:
                r.log["link_cut_method"] = fleet_test.link(plan["cut"], "stop")
                st["cut"] = r.t()
                r.log["link_cut_t"], r.log["link_cut_wall"] = st["cut"], time.time()
                print(f"[{r.t():6.1f}] {plan['cut']} 링크 끊음", flush=True)
    r.wait(keys, track_s * 0.8, every=1.0, extra=maybe_cut)
    wait_stopped(r, [rid for rid in plan["moving"] if rid != plan.get("cut")], track_s, extra=maybe_cut)
    end = time.time() + after_s
    while time.time() < end:
        r.poll()
        time.sleep(1.0)
    if plan.get("cut"):
        fleet_test.link(plan["cut"], "start")
    return r.finish()


def make(sc):
    if sc in SPECIAL:
        return make_special(sc)
    net, lay = layout(sc)
    fleet, spawn = [], []
    for rid, road, node, dist, *_ in lay:
        p, q = _pose(net, road, node, dist)
        lat, lon = FRAME.to_ll(p.x, p.y)
        fleet.append({**CFG[rid], "initial": {"lat": lat, "lon": lon, "heading_deg": round(bearing_deg(q.x - p.x, q.y - p.y), 2)}})
        yaw = math.atan2(q.y - p.y, q.x - p.x)
        spawn.append(f'{CFG[rid]["px4"]["instance"]} {CFG[rid]["profile"]} {p.x:.2f},{p.y:.2f},{Z[CFG[rid]["profile"]]},{yaw:.4f} {rid}')
    fp, sp = LOG_DIR / f"pair_{sc}_fleet.json", LOG_DIR / f"pair_{sc}_spawn.txt"
    fp.write_text(json.dumps(fleet, ensure_ascii=False, indent=1), encoding="utf-8")
    sp.write_text("\n".join(spawn) + "\n", encoding="utf-8")
    print(fp, sp, *spawn, sep="\n")


def run(sc, track_s, after_s=0.0):
    if sc in SPECIAL:
        return run_special(sc, track_s, after_s)
    net, lay = layout(sc)
    on = {v["resource_id"] for v in fleet_test.httpx.get(fleet_test.SERVER + "/ugv", timeout=30).json()}
    lay = [x for x in lay if x[0] in on]                # 서버에 있는 차량만 (한 대만 띄운 시험)
    r = fleet_test.Run(f"pair_{sc}", track_s, rids=[x[0] for x in lay])
    r.log["layout"] = [{"rid": a, "entry_road": b, "node": c, "start_m": d, "dest_road": e, "dest_s_m": round(f, 1)}
                       for a, b, c, d, e, f in lay]
    keys = []
    for rid, _, _, _, road, s in lay:                  # 두 차를 거의 동시에 출발
        key = f"P-{sc[:2].upper()}-{rid}"
        rec = r.go(rid, key, node=node_id_of(net.at(road, s)))
        r.log.setdefault("routes", {})[rid] = r.c.get(f"/ugv/{rid}/route").json()
        if rec["status_code"] == 200:
            keys.append((rid, key))
    r.wait(keys, track_s * 0.8, every=1.0)
    wait_stopped(r, [x[0] for x in lay], track_s)
    end = time.time() + after_s              # 임무가 끝난 뒤에도 기록 (실패 뒤 실제로 서는지·간격)
    while time.time() < end:
        r.poll()
        time.sleep(1.0)
    return r.finish()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=("make", "run"))
    ap.add_argument("scenario", choices=("junction", "head_on", "block", *TURN_SC, *SPECIAL))
    ap.add_argument("--track-s", type=float, default=600)
    ap.add_argument("--after-s", type=float, default=0.0, help="임무가 끝난 뒤 더 기록할 시간 s")
    a = ap.parse_args()
    make(a.scenario) if a.action == "make" else run(a.scenario, a.track_s, a.after_s)


if __name__ == "__main__":
    main()
