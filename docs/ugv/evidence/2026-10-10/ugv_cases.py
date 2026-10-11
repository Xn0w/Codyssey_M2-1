"""UGV 정상·거절·예외 동작 재현 (sim, 실제 서버 앱을 그대로 띄워 HTTP 로 호출).

    UGV_STATE_DIR=/tmp/ugv_cases python -m pytest 없이 그냥:  python ugv_cases.py <출력 JSON>   (저장소 루트에서)

다른 서버(환경·오케스트레이터)는 띄우지 않는다. 시나리오 없음, 배속 200 (시뮬레이션 200초 = 실제 1초).
"""
import json, os, sys, time

os.environ.setdefault("UGV_STATE_DIR", "/tmp/ugv_cases")
os.environ.setdefault("UGV_HISTORY_DIR", os.environ["UGV_STATE_DIR"] + "/history")
os.environ.setdefault("UGV_TIME_SCALE", "200")
os.environ.setdefault("UGV_ENV_URL", "http://127.0.0.1:9")      # 환경 모듈 없음 → UGV 시계가 혼자 흐름
os.environ["UGV_SCENARIO"] = ""
os.environ.setdefault("UGV_TARGET_MODE", "node")    # 10/10 근거는 노드 방식(당시 기본). 도로 위 점은 아래 2번 경우에서 따로 확인
sys.path.insert(0, ".")

from fastapi.testclient import TestClient
from ugv.server import app
import ugv.server as S

T = {"lat": 38.02845, "lon": 128.1309}          # 2019 인제 발화점 부근 (ugv/scenarios/agent_dispatch/task.json)
FAR = {"lat": 38.0985, "lon": 128.1010}         # 도로망 범위 안이지만 가장 가까운 도로 노드가 2 km 넘게 먼 산지
out, n = [], [0]


def rec(case, expect, method, path, body=None, keep=None, note=None, **kw):
    r = c.request(method, path, json=body, **kw)
    b = r.json() if r.content else None
    sub = {k: b.get(k) for k in keep} if keep and isinstance(b, dict) else b
    ok = expect(r.status_code, b) if expect else None
    n[0] += 1
    out.append({"no": n[0], "case": case, "request": {"method": method, "path": path, "body": body, **kw},
                "status": r.status_code, "response": sub, "ok": ok, "note": note})
    print(f"{n[0]:2d} {'OK ' if ok else ('-- ' if ok is None else 'NG ')} {case}: {r.status_code} "
          f"{json.dumps(sub, ensure_ascii=False)[:150]}")
    return b


def wait_task(rid, tid, until=("COMPLETED", "FAILED", "CANCELLED"), timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        b = c.get(f"/ugv/{rid}/task/{tid}").json()
        if b.get("status") in until:
            return b
        time.sleep(0.2)
    return c.get(f"/ugv/{rid}/task/{tid}").json()


EV = ["verdict", "eta_sec", "reason", "detail", "target_node", "path", "stop_point"]
with TestClient(app) as c:
    g = S.fleet.graph
    far_node, far_d = g.nearest_node(FAR["lat"], FAR["lon"])

    # --- 평가 (차는 움직이지 않음) ---
    b = rec("수락: 기본(node 방식)", lambda s, b: b["verdict"] == "ACCEPT",
            "POST", "/ugv/A-ugv1/evaluate", {"task_id": "E1", "decision_id": "D", "target": T}, EV)
    out[-1]["note"] = f"경로 노드 {len(b['path'])}개, ETA {b['eta_sec']}초 = {b['eta_sec']/60:.1f}분 (시뮬레이션)"
    rec("수락: 도로 위 지점(road_point 방식)", lambda s, b: b["verdict"] == "ACCEPT" and bool(b["stop_point"]),
        "POST", "/ugv/A-ugv1/evaluate", {"task_id": "E2", "decision_id": "D", "target": T, "target_mode": "road_point"}, EV)
    rec("거절: 목표가 도로에서 너무 멂", lambda s, b: b["reason"] == "TARGET_UNREACHABLE",
        "POST", "/ugv/A-ugv1/evaluate", {"task_id": "E3", "decision_id": "D", "target": FAR}, EV,
        note=f"가장 가까운 도로 노드까지 {far_d:.0f} m (기준 2000 m)")
    rec("거절: 짐이 적재 한도 초과 (UGV 100 kg)", lambda s, b: b["reason"] == "REQUIRED_CAPABILITY_UNAVAILABLE",
        "POST", "/ugv/A-ugv1/evaluate", {"task_id": "E4", "decision_id": "D", "target": T, "cargo": {"name": "호스 릴", "kg": 500}}, EV)
    tn = c.post("/ugv/A-ugv1/evaluate", json={"task_id": "x", "decision_id": "x", "target": T}).json()["target_node"]["node_id"]
    rec("준비: 목표 노드를 통제 (닿은 도로 전부)", lambda s, b: s == 200, "POST", f"/roads/nodes/{tn}/block", {"blocked": True},
        ["node_id", "blocked", "roads"])
    rec("거절: 목표로 가는 길이 통제됨", lambda s, b: b["reason"] == "ROAD_BLOCKED",
        "POST", "/ugv/A-ugv1/evaluate", {"task_id": "E5", "decision_id": "D", "target": T}, EV)
    c.post(f"/roads/nodes/{tn}/block", json={"blocked": False})

    # --- 주행: 정상 도착 ---
    rec("주행 시작", lambda s, b: b["status"] == "STARTED", "POST", "/ugv/A-ugv1/execute",
        {"task_id": "RUN1", "decision_id": "D", "target": T}, ["status", "eta_sec", "target_node", "duplicate", "tracking_url"])
    rec("같은 주행 요청 재전송 → 새로 출발하지 않음", lambda s, b: b.get("duplicate") is True, "POST", "/ugv/A-ugv1/execute",
        {"task_id": "RUN1", "decision_id": "D", "target": T}, ["status", "duplicate", "current_status"])
    rec("거절: 다른 임무 수행 중", lambda s, b: b["reason"] == "BUSY",
        "POST", "/ugv/A-ugv1/evaluate", {"task_id": "E6", "decision_id": "D", "target": T}, EV)
    rec("주행 중 상태", lambda s, b: any(v["state"] == "RUNNING" for v in b), "GET", "/ugv",
        keep=None, params={"base": "A"})
    out[-1]["response"] = [{k: v.get(k) for k in ("resource_id", "state", "current_node", "current_road_id", "current_task_id")}
                           for v in out[-1]["response"]]
    done = wait_task("A-ugv1", "RUN1")
    n[0] += 1
    out.append({"no": n[0], "case": "정상 도착", "status": 200, "ok": done["status"] == "COMPLETED",
                "response": {k: done.get(k) for k in ("status", "progress", "observation", "timing", "drive_log")},
                "note": "actual_over_eta 는 실제 도착 / ETA. 배속 200 에서는 주행 확인 주기(실제 0.5초 = 시뮬레이션 100초) 단위로 도착을 확정하므로 ETA 보다 늦게 잡힌다"})
    print(n[0], done["status"], json.dumps(done.get("timing"), ensure_ascii=False))

    # --- 주행 중 통제 → 우회 ---
    rec("주행 시작 (우회 시험)", lambda s, b: b["status"] == "STARTED", "POST", "/ugv/B-ugv1/execute",
        {"task_id": "RUN2", "decision_id": "D", "target": T}, ["status", "eta_sec"])
    time.sleep(0.6)
    route = c.get("/ugv/B-ugv1/route").json()
    ahead = [l for l in route["legs"] if l["state"] not in ("DONE",)][3:]
    blk = ahead[0]["road_id"] if ahead else None
    rec("주행 중 앞길 도로 통제", lambda s, b: s == 200, "POST", f"/roads/{blk}/block", {"blocked": True}, ["road_id", "blocked", "blocked_by"])
    done = wait_task("B-ugv1", "RUN2", timeout=60)
    n[0] += 1
    out.append({"no": n[0], "case": "주행 중 우회 후 도착", "status": 200,
                "ok": done["status"] == "COMPLETED" and bool(done.get("reroutes")),
                "response": {k: done.get(k) for k in ("status", "reroutes")}})
    print(n[0], done["status"], done.get("reroutes"))
    c.post(f"/roads/{blk}/block", json={"blocked": False})

    # --- 주행 중 목표가 막힘 → 실패 ---
    rec("주행 시작 (우회 불가 시험)", lambda s, b: b["status"] == "STARTED", "POST", "/ugv/A-fire1/execute",
        {"task_id": "RUN3", "decision_id": "D", "target": T}, ["status", "eta_sec"])
    time.sleep(0.3)
    c.post(f"/roads/nodes/{tn}/block", json={"blocked": True})
    done = wait_task("A-fire1", "RUN3")
    st = c.get("/ugv/A-fire1/state").json()
    n[0] += 1
    out.append({"no": n[0], "case": "주행 중 목표가 막혀 우회 불가 → 실패", "status": 200,
                "ok": done["status"] == "FAILED" and st["state"] == "READY",
                "response": {"task": {k: done.get(k) for k in ("status", "error", "reroutes")}, "vehicle_state": st["state"]},
                "note": "고장이 아니므로 차는 READY"})
    print(n[0], done["status"], done.get("error"), st["state"])
    c.post(f"/roads/nodes/{tn}/block", json={"blocked": False})

    # --- 정지 ---
    c.post("/ugv/A-ugv1/execute", json={"task_id": "RUN4", "decision_id": "D", "target": {"lat": 38.0985, "lon": 128.2010}})
    time.sleep(0.3)
    rec("정지 요청", lambda s, b: b["cancelled_task"] == "RUN4", "POST", "/ugv/A-ugv1/stop",
        keep=["cancelled_task", "state", "current_node"])
    rec("정지 후 임무 상태", lambda s, b: b["status"] == "CANCELLED", "GET", "/ugv/A-ugv1/task/RUN4", keep=["status", "error"])
    rid = c.get("/history/runs").json()["current"]

json.dump({"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "driver": "sim", "time_scale": os.environ["UGV_TIME_SCALE"],
           "history_run_id": rid, "cases": out}, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
print("all ok:", all(x["ok"] in (True, None) for x in out), "run", rid)
