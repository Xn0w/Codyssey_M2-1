"""4단계: 총괄(orchestrator 엔진, 프로세스 안) ↔ UGV 서버(HTTP) 폐루프. 운용자 역할(복귀 요청)만 시험 스크립트가 한다.

  python logs/ugv/stage4/orch_loop.py --url http://127.0.0.1:8100 --scenario loop --tag sim_loop
  시나리오
    loop     A·B 지역 UGV·소방차 임무 4건 → 배정·도착·완료·해제 → (운용자) 소속 거점 복귀 → READY 확인
    fault    A-ugv1 임무 중 고장 주입 → FAULTED, 차가 서기 전 같은 차 재배정 없음, 다른 차 인계
    blocked  A-ugv1 출발 도로에 고장 차(B-fire1, 시험 배치) → 막힘 실패 → 같은 막힌 차 반복 배정 여부
기록: logs/ugv/stage4/orch_<tag>.json (총괄 장부 사건 + UGV 상태 시계열)
"""
import argparse
import json
import math
import pathlib
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from orchestrator.engine import Orchestrator  # noqa: E402
from orchestrator.env_adapter import FixtureEnv  # noqa: E402
from orchestrator.ledger import Ledger  # noqa: E402
from orchestrator.resources import UgvClient  # noqa: E402

MON = {"X-ADAIR-Monitor": "1"}          # 감시 요청은 총괄 연락으로 세지 않는다
OUT = ROOT / "logs" / "ugv" / "stage4"

# A 지역: 인제119 출입 지점 근처 도로 (표준 목표), B 지역: 기린119 근처 도로
TARGETS = {
    "A_ROAD": {"lat": 38.0277, "lon": 128.1303, "cell_id": "A_ROAD"},
    "A_ROAD2": {"lat": 38.07212, "lon": 128.18129, "cell_id": "A_ROAD2"},
    "B_ROAD": {"lat": 37.9580, "lon": 128.3195, "cell_id": "B_ROAD"},
    "B_ROAD2": {"lat": 37.9557, "lon": 128.3179, "cell_id": "B_ROAD2"},
}


class Loop:
    def __init__(self, url, tag):
        self.url, self.tag = url.rstrip("/"), tag
        self.c = httpx.Client(base_url=self.url, timeout=30, headers=MON)
        db = pathlib.Path(tempfile.mkdtemp()) / "orch.db"
        self.orch = Orchestrator(Ledger(str(db)), FixtureEnv(), ugv=UgvClient(self.url))
        self.t0 = time.time()
        self.log = {"tag": tag, "url": url, "start_local": time.strftime("%F %T"), "timeline": [], "notes": [],
                    "dispatch": [], "operator": []}

    def t(self):
        return round(time.time() - self.t0, 1)

    def states(self):
        return {s["resource_id"]: s for s in self.c.get("/ugv").json()}

    def snap(self, label=""):
        st = self.states()
        rec = {"t": self.t(), "label": label, "v": {r: {"state": s["state"], "mission": s["mission_state"],
                                                         "speed": s["speed_mps"], "task": s["current_task_id"],
                                                         "fault": s["fault"], "phys": s.get("physical_state"),
                                                         "pos": [s["position"]["lat"], s["position"]["lon"]]}
                                                     for r, s in st.items()},
               "reservations": self.orch.ledger.reservations()}
        self.log["timeline"].append(rec)
        return rec

    def submit(self, rid, target, types):
        task, _ = self.orch.submit_task({"request_id": rid, "incident_id": "INC-STAGE4", "kind": "GROUND_SUPPORT",
                                         "target": dict(target),
                                         "requirements": {"resource_types": list(types), "sensor": None,
                                                          "needs_env_ack": False}})
        return task

    def dispatch(self, task):
        out = self.orch.dispatch(task.task_id)
        self.log["dispatch"].append({"t": self.t(), "task": task.task_id, "out": out})
        print(f"[{self.t():7.1f}] 배정 {task.task_id}: {out.get('status')} {out.get('resource_id')} 제외 {out.get('excluded')}",
              flush=True)
        return out

    def step(self, label=""):
        ups = self.orch.poll()
        if hasattr(self.orch, "ugv_contact"):
            self.orch.ugv_contact()               # 총괄 서버 추적 루프와 같게 (9c04b30)
        for u in ups or []:
            print(f"[{self.t():7.1f}] 추적 {json.dumps(u, ensure_ascii=False, default=str)[:220]}", flush=True)
        dp = self.orch.dispatch_pending(allow_llm_call=False)
        for tid, r in (dp.get("results") or {}).items():
            self.log["dispatch"].append({"t": self.t(), "task": tid, "out": r, "via": "dispatch_pending"})
            print(f"[{self.t():7.1f}] 재배정 {tid}: {r.get('status')} {r.get('resource_id')} 제외 {r.get('excluded')}", flush=True)
        return self.snap(label)

    def attempts(self, task_id=None):
        return self.orch.ledger.list_attempts(task_id)

    def wait(self, cond, timeout, every=2.0, label=""):
        end = time.time() + timeout
        while time.time() < end:
            s = self.step(label)
            if cond(s):
                return True
            time.sleep(every)
        return False

    def go_home(self, rid):
        """운용자 역할: 해제된 차를 소속 거점 출입 지점으로 (총괄에 복귀 기능이 없어 UGV 서버에 직접)."""
        st = self.c.get(f"/ugv/{rid}/state").json()
        acc = st["station"]["access_point"]
        body = {"task_id": f"HOME-{rid}-{int(time.time())}", "decision_id": "OPERATOR-HOME",
                "target_node": f"RP:{acc['road_id']}:{acc['s_m']:.1f}"}
        # 운용자 호출은 총괄 연락과 같은 경로(차량 요청)로 센다 — 감시 머리표 없이
        r = httpx.post(f"{self.url}/ugv/{rid}/execute", json=body, timeout=60)
        rec = {"t": self.t(), "rid": rid, "body": body, "status": r.status_code, "resp": r.json()}
        self.log["operator"].append(rec)
        print(f"[{self.t():7.1f}] 운용자 복귀 {rid}: {r.status_code} {r.json().get('status')} {r.json().get('error')}", flush=True)
        return rec

    def finish(self):
        self.log["end_local"] = time.strftime("%F %T")
        self.log["ledger_events"] = [{k: e.get(k) for k in ("seq", "event_type", "task_id", "attempt_id", "resource_id",
                                                             "result", "reason", "detail")}
                                     for e in self.orch.ledger.events()]
        self.log["attempts"] = self.attempts()
        self.log["ugv_events"] = {r: self.c.get(f"/ugv/{r}/events?limit=200").json() for r in self.states()}
        p = OUT / f"orch_{self.tag}.json"
        p.write_text(json.dumps(self.log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        print("기록:", p)


def sc_loop(L, args):
    jobs = [("A_ROAD", ("UGV",)), ("A_ROAD2", ("FIRE_ENGINE",)), ("B_ROAD", ("UGV",)), ("B_ROAD2", ("FIRE_ENGINE",))]
    tasks = []
    for i, (tg, ty) in enumerate(jobs):
        t = L.submit(f"S4-LOOP-{i}-{L.tag}", TARGETS[tg], ty)
        out = L.dispatch(t)
        tasks.append((t, out))
    # 해제까지
    def released(_):
        atts = [a for t, _o in tasks for a in L.attempts(t.task_id)]
        return atts and all(a["substatus"] in ("RELEASED", "FAILED") for a in atts) and \
            all(L.orch.ledger.get_task(t.task_id).purpose_status in ("COMPLETED", "FAILED", "HOLD") for t, _ in tasks)
    ok = L.wait(released, args.track_s, label="to_release")
    L.log["notes"].append({"released_all": ok,
                           "purpose": {t.task_id: L.orch.ledger.get_task(t.task_id).purpose_status for t, _ in tasks},
                           "attempts": {a["attempt_id"]: [a["resource_id"], a["substatus"]] for t, _ in tasks
                                        for a in L.attempts(t.task_id)}})
    # 운용자 복귀
    rids = sorted({a["resource_id"] for t, _ in tasks for a in L.attempts(t.task_id)})
    for rid in rids:
        L.go_home(rid)
    def home_ready(s):
        return all(s["v"][r]["state"] == "READY" and s["v"][r]["task"] is None and (s["v"][r]["speed"] or 0) < 0.1
                   for r in rids)
    time.sleep(3)
    ok2 = L.wait(home_ready, args.track_s, label="to_home")
    L.log["notes"].append({"home_ready_all": ok2})


def sc_fault(L, args):
    t = L.submit(f"S4-FAULT-{L.tag}", TARGETS["A_ROAD"], ("UGV",))
    out = L.dispatch(t)
    rid = out.get("resource_id")
    L.wait(lambda s: (s["v"][rid]["speed"] or 0) > 8, 120, label="accel")
    r = httpx.post(f"{L.url}/ugv/{rid}/_test/fault", json={"code": "VEHICLE_FAULT", "detail": "시험: 주행 중 고장"}, timeout=30)
    L.log["notes"].append({"fault_injected_t": L.t(), "rid": rid, "resp": r.json()})
    print(f"[{L.t():7.1f}] 고장 주입 {rid}", flush=True)
    # 서기 전·후 배정 기록: 같은 차가 서기 전에 다시 배정되면 안 된다
    stop_t = None
    end = time.time() + args.track_s
    while time.time() < end:
        s = L.step("after_fault")
        v = s["v"][rid]
        if stop_t is None and (v["speed"] or 0) < 0.1 and v["mission"] not in ("DRIVING", "STOPPING"):
            stop_t = L.t()
            L.log["notes"].append({"faulted_vehicle_stopped_t": stop_t, "phys": v["phys"]})
        others = [a for a in L.attempts(t.task_id) if a["resource_id"] != rid]
        if others and any(a["substatus"] in ("STARTED", "ARRIVED", "OBSERVED", "RELEASED") for a in others):
            # 다른 차 인계 시작 확인 (장거리면 도착까지 기다리지 않는다). 그 뒤 30 s 더 본다
            L.log["notes"].append({"handover_started_t": L.t(), "to": others[-1]["resource_id"]})
            L.wait(lambda s: False, 30, label="after_handover")
            break
        time.sleep(2)
    L.log["notes"].append({"attempts": [[a["resource_id"], a["substatus"], a.get("created_at")] for a in L.attempts(t.task_id)],
                           "purpose": L.orch.ledger.get_task(t.task_id).purpose_status})


def sc_blocked(L, args):
    t = L.submit(f"S4-BLOCK-{L.tag}", TARGETS["A_ROAD2"], ("UGV",))

    def fault():
        r = httpx.post(f"{L.url}/ugv/B-fire1/_test/fault", json={"code": "VEHICLE_FAULT", "detail": "시험: 도로 위 고장 정지"}, timeout=30)
        L.log["notes"].append({"blocker_fault": r.json().get("state"), "t": L.t(), "late": args.late})
    if not args.late:
        fault()
    out = L.dispatch(t)
    if args.late:                        # 배정·출발 뒤에 앞 차가 고장으로 선다
        L.wait(lambda s: (s["v"]["A-ugv1"]["speed"] or 0) > 3, 60, label="depart")
        fault()
    end = time.time() + args.track_s
    while time.time() < end:
        L.step("blocked")
        atts = L.attempts(t.task_id)
        if len([a for a in atts if a["resource_id"] == "A-ugv1"]) >= 3:
            L.log["notes"].append({"repeated_assignment_A_ugv1": len(atts)})
            break
        if L.orch.ledger.get_task(t.task_id).purpose_status in ("COMPLETED", "FAILED"):
            break
        time.sleep(2)
    L.log["notes"].append({"attempts": [[a["resource_id"], a["substatus"]] for a in L.attempts(t.task_id)],
                           "purpose": L.orch.ledger.get_task(t.task_id).purpose_status,
                           "hold": L.orch.ledger.get_task(t.task_id).hold_reason})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8100")
    ap.add_argument("--scenario", choices=("loop", "fault", "blocked"), required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--track-s", type=float, default=900)
    ap.add_argument("--late", action="store_true", help="blocked: 배정·출발 뒤에 고장 주입")
    a = ap.parse_args()
    L = Loop(a.url, a.tag)
    L.snap("start")
    try:
        {"loop": sc_loop, "fault": sc_fault, "blocked": sc_blocked}[a.scenario](L, a)
    finally:
        L.finish()


if __name__ == "__main__":
    main()
