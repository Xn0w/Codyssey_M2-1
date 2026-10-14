"""교차로 회전 도중 정차 갇힘 Gazebo 재현 (2026-10-11 c23 A-fire1 정차 자세 그대로 스폰, 위치 ±0.2 m).
판정: 서버가 고른 출발 도로(평가 응답 direction.start_road), 가장 가까운 도로(예전 선택), 복귀 평가·출동 평가 승인, 복귀 실행 도착·도로 이탈.
  bash logs/ugv/stage4/run_sc_wt.sh c24_junc0 <spawn> logs/ugv/stage4/single_fire1_fleet.json .venv/Scripts/python.exe logs/ugv/stage4/junction_verify.py --label 0
"""
import argparse
import json
import sys
import time

sys.path.insert(0, ".")
from ugv.geo import FRAME  # noqa: E402
from ugv.roads import RoadNetwork  # noqa: E402
from ugv.tools import fleet_test  # noqa: E402

RID = "A-fire1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="0")
    a = ap.parse_args()
    run = fleet_test.Run(f"junc{a.label}", 900, rids=[RID])
    net = RoadNetwork()
    _, _, ll = fleet_test.targets()
    st = run.c.get(f"/ugv/{RID}/state").json()
    x, y = FRAME.to_xy(st["position"]["lat"], st["position"]["lon"])
    near = sorted(net.near(x, y, 6.0).items(), key=lambda kv: kv[1])
    acc = st["station"]["access_point"]
    out = {"label": a.label, "position": st["position"], "heading_deg": st["heading_deg"],
           "nearest_roads": [(r, round(d, 2)) for r, d in near], "old_start_road": near[0][0] if near else None}
    ev_home = run.c.post(f"/ugv/{RID}/evaluate", json={"task_id": f"JH{a.label}", "decision_id": "D-JH",
                                                         "target_node": f"RP:{acc['road_id']}:{acc['s_m']:.1f}"}).json()
    tgt = ll("A", 1800, 1500)
    ev_go = run.c.post(f"/ugv/{RID}/evaluate", json={"task_id": f"JG{a.label}", "decision_id": "D-JG",
                                                       "target": {"lat": tgt[0], "lon": tgt[1]}}).json()
    out["home_eval"] = {"verdict": ev_home.get("verdict"), "eta": ev_home.get("eta_sec"), "detail": ev_home.get("detail"),
                        "start_road": (ev_home.get("approach") or {}).get("direction", {}).get("start_road"),
                        "start_toward": (ev_home.get("approach") or {}).get("direction", {}).get("start_toward_node")}
    out["go_eval"] = {"verdict": ev_go.get("verdict"), "eta": ev_go.get("eta_sec"), "detail": ev_go.get("detail")}
    print(json.dumps(out, ensure_ascii=False), flush=True)
    if ev_home.get("verdict") == "ACCEPT":
        rec = run.home(RID, f"JX{a.label}")
        if rec["status_code"] == 200:
            run.wait([(RID, f"JX{a.label}")], 600, every=3.0)
        t = run.c.get(f"/ugv/{RID}/task/JX{a.label}").json()
        out["home_exec"] = {"status": t.get("status"), "physical_state": t.get("physical_state"), "reason": t.get("reason")}
    run.log["junction_verify"] = out
    print(json.dumps({"home_exec": out.get("home_exec")}, ensure_ascii=False), flush=True)
    print("기록:", run.finish())


if __name__ == "__main__":
    main()
