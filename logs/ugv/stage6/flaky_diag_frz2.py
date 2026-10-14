# -*- coding: utf-8 -*-
"""간헐 실패 진단 v3 (2026-10-13 독립 검토 + 배속 간헐 실패 진단 추가 보완 + 진단 v2·판정 v3.1 반영 검증 통합 보완 1~4·7 반영).
장면 = test_closed_loop_fault_redecision_other_resource_return_ready 의 1)~5) (30배속, sim 드라이버, 실제 총괄·UGV 서버). 시험 assertion 은 바꾸지 않는다.

회차마다 <out_dir>/run<k>.jsonl 에 생성 순간부터 한 줄씩 기록 (외부 시간 초과로 끝나도 남음):
  EVENT       차량 이벤트 전부 (Vehicle._event 를 감싸 생성 즉시 복사 — 운영 코드의 events 200개·임무 50개 제한은 그대로)
  PLAN        _drive 호출: 계획 순번·차량·sim/wall 시각·경로 도로·계획선 좌표(복사)
  APPROACH    _approach 호출: 회피 대상(extra_avoid)·결과 상태·경로 도로·계획선 좌표
  FOLLOW      driver.follow: 전송 경유점(복사)·미션 seq 전/후·성공/예외 원문
  BLOCKED_CALL blocked_by_vehicle 호출 순간의 원시 위치(A·B)·heading·B 경로상 s·이전 막힘 이력 (무거운 지도 계산은 하지 않음 — 사후 flaky_post.py)
  FAULT_TIMELINE 고장 조건 첫 충족(관측)·요청 시작·응답 시각, 서버 FAULT 이벤트 sim 시각
  TIMING      차량 sim dt(driver.step 인수), 감독(tick)·교통 판단(traffic.tick) 실제 간격·소요, 진단 hook 소요 합계
  RESULT      분류 ARRIVED / NOT_ARRIVED / PRECONDITION_FAILED / TIMEOUT / EXCEPTION, 전체 traceback, 최종 수집(임무·장부 — 항목마다 따로 try)
'ARRIVED' 는 대체 차량 도착까지만 — 기존 시험의 관측·반납·복귀·고장차 해제까지 본 회귀 합격 수가 아니다. 20회는 장면 관찰이며 원인 확정이 아니다.
계측 자체가 30배속 실행 간격을 바꿀 수 있다 (TIMING 으로 확인). 이 실패율을 이전 기록과 단순 비교해 개선·악화를 확정하지 않는다.
실행 (ADAIR_wt_integ 에서): python ../ADAIR/logs/ugv/stage6/flaky_diag.py <N> <out_dir>"""
import json
import math
import statistics
import sys
import tempfile
import time
import traceback
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, ".")
from orchestrator.engine import Orchestrator                      # noqa: E402
from orchestrator.env_adapter import FixtureEnv                   # noqa: E402
from orchestrator.ledger import Ledger                            # noqa: E402
from orchestrator.resources import UgvClient                      # noqa: E402
from ugv.geo import FRAME                                         # noqa: E402
from ugv.tests import test_orchestrator_closed_loop as T          # noqa: E402

NET = T.NET


class Precondition(Exception):
    pass


class Rec:
    """회차 기록기: 한 줄씩 즉시 기록 (line buffered), hook 소요 누적."""
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8", buffering=1)
        self.hook_s = 0.0
        self.n = 0

    def w(self, kind, **kw):
        """생성 순간 직렬화 (= 스냅샷 — 이후 객체가 바뀌어도 기록은 그대로). 기록 실패는 DIAG_ERROR 로만 남기고 원래 명령에 전파하지 않는다."""
        t0 = time.perf_counter()
        try:
            self.f.write(json.dumps({"kind": kind, "wall": round(time.time(), 4), **kw}, ensure_ascii=False, default=str) + "\n")
        except Exception as e:  # noqa: BLE001
            try:
                self.f.write(json.dumps({"kind": "DIAG_ERROR", "of": kind, "error": repr(e)}) + "\n")
            except Exception:  # noqa: BLE001
                pass
        self.n += 1
        self.hook_s += time.perf_counter() - t0

    def close(self):
        self.f.close()


def pose(v):
    t = v.driver.telemetry()
    return None if t is None else {"x": round(t.x, 3), "y": round(t.y, 3), "heading": round(t.heading_deg, 2), "speed": round(t.speed_mps or 0, 3)}


def pts(route):
    return [[round(x, 2), round(y, 2)] for x, y in (getattr(route, "pts", None) or [])]


def instrument(v, R, timing):
    clock = v.clock
    o_event, o_drive, o_appr, o_block = v._event, v._drive, v._approach, v.blocked_by_vehicle
    o_follow, o_step, o_tick = v.driver.follow, v.driver.step, v.tick
    plan_no = {"n": 0}
    rid = v.resource_id

    def event(name, /, **kw):
        e = o_event(name, **kw)
        R.w("EVENT", vehicle=rid, e=e)
        return e

    async def drive(plan, *a, **k):
        plan_no["n"] += 1
        R.w("PLAN", vehicle=rid, no=plan_no["n"], sim_t=round(clock.now(), 3), road_ids=list(plan.route.road_ids), pts=pts(plan.route),
            mission_seq_before=getattr(v.driver.progress(), "mission_seq", None), pose=pose(v))
        return await o_drive(plan, *a, **k)

    def approach(body, start, v0, extra_avoid=None):
        res = o_appr(body, start, v0, extra_avoid)
        R.w("APPROACH", vehicle=rid, sim_t=round(clock.now(), 3), extra_avoid=extra_avoid, status=getattr(res, "status", None),
            reason=getattr(res, "reason", None), road_ids=list(res.route.road_ids) if getattr(res, "route", None) is not None else None,
            pts=pts(res.route) if getattr(res, "route", None) is not None else None)
        return res

    async def follow(items, *a, **k):
        before = getattr(v.driver.progress(), "mission_seq", None)
        R.w("FOLLOW_SEND", vehicle=rid, sim_t=round(clock.now(), 3), items=[list(i) if isinstance(i, (list, tuple)) else repr(i) for i in items], seq_before=before)
        try:
            r = await o_follow(items, *a, **k)
            R.w("FOLLOW_RESULT", vehicle=rid, sim_t=round(clock.now(), 3), seq_before=before, seq_after=getattr(v.driver.progress(), "mission_seq", None), ok=True, ret=r)
            return r
        except Exception as e:  # noqa: BLE001
            R.w("FOLLOW_RESULT", vehicle=rid, sim_t=round(clock.now(), 3), seq_before=before, ok=False, error=f"{type(e).__name__}: {e}")
            raise

    async def blocked(other_id, waited_s, immovable, **kw):          # kw: episode (막힘 에피소드 수정판 vehicle.blocked_by_vehicle)
        other = next((p for p in v.peers() if p.resource_id == other_id), None)
        R.w("BLOCKED_CALL", vehicle=rid, other=other_id, sim_t=round(clock.now(), 3), waited_s=waited_s, immovable=immovable,
            self_pose=pose(v), self_s=round(v._s_now(), 2) if v.speed is not None else None,
            other_pose=pose(other) if other else None, prior_blocked=(v.current_task() or {}).get("blocked", []),
            episode=list(kw["episode"]) if kw.get("episode") is not None else None, drive_gen=getattr(v, "drive_gen", None))
        return await o_block(other_id, waited_s, immovable, **kw)

    def step(dt):
        timing.setdefault(f"{rid}_dt", []).append(dt)
        return o_step(dt)

    last = {"t": None}

    async def tick(*a, **k):
        t0 = time.perf_counter()
        if last["t"] is not None:
            timing.setdefault(f"{rid}_tick_interval_wall", []).append(t0 - last["t"])
        last["t"] = t0
        r = await o_tick(*a, **k)
        timing.setdefault(f"{rid}_tick_dur_wall", []).append(time.perf_counter() - t0)
        return r
    v._event, v._drive, v._approach, v.blocked_by_vehicle = event, drive, approach, blocked
    v.driver.follow, v.driver.step, v.tick = follow, step, tick


def instrument_traffic(fleet, timing):
    tr = getattr(fleet, "traffic", None)
    if tr is None:
        return
    o = tr.tick
    last = {"t": None}

    async def tick(*a, **k):
        t0 = time.perf_counter()
        if last["t"] is not None:
            timing.setdefault("traffic_interval_wall", []).append(t0 - last["t"])
        last["t"] = t0
        r = await o(*a, **k)
        timing.setdefault("traffic_dur_wall", []).append(time.perf_counter() - t0)
        return r
    tr.tick = tick


def stats(xs):
    if not xs:
        return None
    s = sorted(xs)
    return {"n": len(s), "mean": round(statistics.mean(s), 4), "p95": round(s[int(0.95 * (len(s) - 1))], 4), "max": round(s[-1], 4)}


def need(ok, what):
    if not ok:
        raise Precondition(what)


def until_first(orch, cond, timeout_s, every=0.3):
    """T._until 와 같은 주기 — 조건을 처음 '관측'한 wall 시각을 함께 돌려준다."""
    end = time.time() + timeout_s
    while time.time() < end:
        orch.poll()
        if cond():
            return True, time.time()
        time.sleep(every)
    return False, None


def one(k, out_dir, fault_s=None, scale=None, frozen_a=None):
    tmp = Path(tempfile.mkdtemp())
    mp = pytest.MonkeyPatch()
    R = Rec(out_dir / f"run{k:02d}.jsonl")
    timing, res = {}, {"class": "EXCEPTION"}
    fleet = orch = task_id = None
    att = []
    try:
        fleet, app = T._loop(tmp, mp) if scale is None else T._loop(tmp, mp, scale=scale)
        import os as _os
        R.w("SETUP", scale=getattr(fleet.vehicles["A-ugv1"].clock, "scale", None), tick_wall_s=0.05, fault_s=fault_s,
            block_avoid=_os.getenv("UGV_BLOCK_AVOID", "origin"))
        with TestClient(app) as http:
            ugv = UgvClient(base_url="http://testserver", client=http)
            orch = Orchestrator(Ledger(str(tmp / "orch.db")), FixtureEnv(), ugv=ugv)
            A, B = fleet.vehicles["A-ugv1"], fleet.vehicles["A-ugv2"]
            for v in (A, B):
                instrument(v, R, timing)
            instrument_traffic(fleet, timing)
            lat, lon = FRAME.to_ll(A.access.x - 900, A.access.y - 700)
            task = T._submit(orch, "LOOP-A", lat, lon)
            task_id = task.task_id
            out = orch.dispatch(task.task_id)
            R.w("DISPATCH", no=1, out={k2: out.get(k2) for k2 in ("status", "resource_id", "attempt_id")})
            need(out["status"] == "STARTED" and out["resource_id"] == "A-ugv1", "dispatch1")
            att.append(out["attempt_id"])
            if fault_s is None:
                ok, t_obs = until_first(orch, lambda: A.state == "DRIVING" and (A.driver.telemetry().speed_mps or 0) > 3, 30)
                need(ok, "A driving >3 m/s")
            else:
                # 개입 비교: 경로상 s 가 [lo, hi] 안에 들어오면 주입 (벽시계 5 ms 간격으로 확인 — orch.poll 없이). 창을 지나치면 전제 실패
                lo, hi = fault_s
                end = time.time() + 60
                while time.time() < end and not (A.state == "DRIVING" and A.speed is not None and A._s_now() >= lo):
                    time.sleep(0.005)
                s_now = A._s_now() if A.speed is not None else None
                t_obs = time.time()
                R.w("FAULT_WINDOW", lo=lo, hi=hi, s_observed=s_now)
                need(s_now is not None and lo <= s_now <= hi, f"fault window [{lo},{hi}] missed (s={s_now})")
            pa = pose(A)
            t_req = time.time()
            r = http.post("/ugv/A-ugv1/_test/fault", json={"code": "VEHICLE_FAULT", "detail": "진단"})
            t_resp = time.time()
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:300]
            fault_ev = next((e for e in reversed(A.events) if "FAULT" in e.get("event", "")), None)
            R.w("FAULT_TIMELINE", cond_observed_wall=t_obs, request_wall=t_req, response_wall=t_resp, pose_at_request=pa,
                s_at_request=round(A._s_now(), 2), http_code=r.status_code, body=body, server_fault_event=fault_ev,
                mission_seq_at_request=getattr(A.driver.progress(), "mission_seq", None),
                progress_at_request=(lambda g: None if g is None else {"current": g.current, "total": g.total})(A.driver.progress()))
            need(r.status_code == 200, "fault http")
            need(T._until(orch, lambda: orch.ledger.get_attempt(out["attempt_id"])["substatus"] == "FAULTED", 15), "attempt FAULTED")
            need(T._until(orch, lambda: A.driver.telemetry().speed_mps < 0.2, 20), "A stopped")
            if frozen_a is not None:
                # 고정 장면 (2026-10-13 Codex 답변 1548 (가)): 실제 고장·정지 뒤 A 를 원래 실패 회차의 최종 자세에 배치하고 움직이지 않게 고정.
                # 시험 전용 초기 조건 — 운영 순간이동·복구 구현 아님. 배치 뒤 2 s(시뮬) 동안 이동 0.05 m 미만인지 확인 (아니면 전제 실패)
                fx, fy, fh = frozen_a
                drv = A.driver
                drv.x, drv.y, drv.heading, drv.v = fx, fy, fh, 0.0
                drv.frozen = True
                # frz2 (Codex 1557): 배치 전 실제 정지 위치(경로 s)가 회차마다 달라 A 내부 진행 상태가 달랐다 → 배치 자세에 맞춰
                # A 계획선 진행 색인(_near_i)을 전역 최근접으로 다시 정한다 (원래 실패 회차는 s ≈ 46 m 부근). 전·후 값을 기록
                near_before, s_before = A._near_i, (A._s_now() if A.speed is not None else None)
                if A.speed is not None:
                    A._near_i = min(range(len(A.speed.pts)), key=lambda i: math.hypot(A.speed.pts[i][0] - fx, A.speed.pts[i][1] - fy))
                A_state_fix = {"near_i_before": near_before, "s_before": None if s_before is None else round(s_before, 2),
                               "near_i_after": A._near_i, "s_after": round(A._s_now(), 2) if A.speed is not None else None,
                               "a_state": A.state, "a_seq": getattr(A.driver.progress(), "mission_seq", None)}
                t0 = A.clock.now()
                T._until(orch, lambda: A.clock.now() - t0 >= 2.0, 30)
                held = math.hypot(drv.x - fx, drv.y - fy)
                import hashlib
                sid = hashlib.sha1(json.dumps({"a": [fx, fy, fh], "b": pose(B), "a_prof": [A.profile.body_length_m, A.profile.body_width_m,
                                    A.profile.rear_axle_from_center_m]}, sort_keys=True).encode()).hexdigest()[:12]
                R.w("A_FROZEN", target=[fx, fy, fh], pose=pose(A), moved_m=round(held, 3), b_pose=pose(B), scene_id=sid, a_state_fix=A_state_fix,
                    fixture_version="frz2",
                    basis="원래 실패 회차 A 최종 자세 고정 (flaky_diag_v3 run00)")
                need(held < 0.05, f"frozen A moved {held:.3f} m")
            R.w("A_STOP", pose=pose(A), s_on_route=round(A._s_now(), 2), sim_t=round(A.clock.now(), 3), frozen=frozen_a is not None,
                mission_seq=getattr(A.driver.progress(), "mission_seq", None),
                profile={"body_length_m": A.profile.body_length_m, "body_width_m": A.profile.body_width_m,
                         "rear_axle_from_center_m": A.profile.rear_axle_from_center_m},
                b_profile={"body_length_m": B.profile.body_length_m, "body_width_m": B.profile.body_width_m,
                           "rear_axle_from_center_m": B.profile.rear_axle_from_center_m},
                origin_basis="sim 드라이버 텔레메트리 원점 (뒤축 중심 가정 — 사후 계산에서 근사로 표시)")
            if frozen_a is not None:
                # frz2 상태 서명 (Codex 답변 1618): B 출동 직전 A 의 교통·감독 관련 내부 상태와 교통 모듈 실제 예측 표본 해시.
                # 같은 fixture 로 합칠지는 이 서명이 같은지로 본다 (다르면 합치지 않음)
                import hashlib
                def _h(o):
                    return hashlib.sha1(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()[:12]
                prog = A.driver.progress()
                pred = None
                tr = getattr(fleet, "traffic", None)
                try:
                    pr = tr._predict(A) if tr is not None else None
                    pred = None if pr is None else {"n": len(pr.samples), "static": pr.static, "committed_m": round(pr.committed_m, 2),
                                                    "hash": _h([[round(x, 2) for x in smp] for smp in pr.samples])}
                except Exception as e:  # noqa: BLE001
                    pred = {"error": repr(e)[:200]}
                st = {"state": A.state, "seq": getattr(prog, "mission_seq", None), "progress": [getattr(prog, "current", None), getattr(prog, "total", None), getattr(prog, "finished", None)],
                      "stop_sup": A._stop_sup is not None, "stop_cut_active": bool(A.stop_cut_active), "command_uncertain": bool(getattr(A, "command_uncertain", False)),
                      "stop_path_pts": _h(A.stop_path_pts), "speed_plan": None if A.speed is None else _h([[round(c, 2) for c in q] for q in A.speed.pts]),
                      "driver_path": _h([list(map(lambda z: round(z, 2), it[:3])) for it in (A.driver.path or [])]), "driver_k": A.driver.k,
                      "near_i": A._near_i, "s": round(A._s_now(), 2) if A.speed is not None else None, "pose": pose(A), "hold": A.hold is not None}
                R.w("A_STATE_SIG", sig=_h({k: v for k, v in st.items() if k != "pose"}), pred_sig=None if not pred or "hash" not in pred else pred["hash"],
                    state=st, traffic_pred=pred, scene_id=sid, fixture_version="frz2")
            out2 = orch.dispatch(task.task_id)
            R.w("DISPATCH", no=2, out={k2: out2.get(k2) for k2 in ("status", "resource_id", "attempt_id")})
            need(out2["status"] == "STARTED" and out2["resource_id"] == "A-ugv2", "dispatch2 A-ugv2")
            att.append(out2["attempt_id"])
            done = T._until(orch, lambda: orch.ledger.get_attempt(out2["attempt_id"])["substatus"] in ("ARRIVED", "OBSERVED", "APPLIED", "RELEASED", "FAULTED", "UNKNOWN")
                            or ([t for t in fleet.store.tasks.values() if t["resource_id"] == "A-ugv2"] or [{}])[-1].get("status") in ("FAILED", "COMPLETED"), 240)
            bt = [t for t in fleet.store.tasks.values() if t["resource_id"] == "A-ugv2"][-1]
            res.update({"b_status": bt["status"], "b_result": bt.get("mission_result"), "b_error": bt.get("error")})
            res["class"] = "TIMEOUT" if not done else ("ARRIVED" if bt["status"] == "COMPLETED" and bt.get("mission_result") == "ARRIVED" else "NOT_ARRIVED")
    except Precondition as e:
        res.update({"class": "PRECONDITION_FAILED", "precondition": str(e)})
    except Exception:  # noqa: BLE001
        res.update({"class": "EXCEPTION", "traceback": traceback.format_exc()})
    finally:
        final = {}
        for name, fn in (("ugv_tasks", lambda: [t for t in fleet.store.tasks.values() if t["resource_id"] in ("A-ugv1", "A-ugv2")]),
                         ("attempts", lambda: {a: orch.ledger.get_attempt(a) for a in att}),
                         ("ledger_events", lambda: orch.ledger.events(task_id))):
            try:
                final[name] = fn()
            except Exception:  # noqa: BLE001
                final[name + "_error"] = traceback.format_exc()
        R.w("TIMING", hook_wall_s=round(R.hook_s, 4), records=R.n, **{k2: stats(v2) for k2, v2 in timing.items()})
        R.w("RESULT", **res, final=final)
        R.close()
        mp.undo()
    return res


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--fault-s", nargs=2, type=float, default=None, help="개입: 경로상 s 범위 [lo hi] 에서 고장 주입")
    ap.add_argument("--scale", type=float, default=None, help="개입: 배속 (기본 시험 값 30)")
    ap.add_argument("--frozen-a", nargs=3, type=float, default=None, help="고정 장면: 고장·정지 뒤 A 를 x y heading 에 배치·고정")
    a = ap.parse_args()
    n, out_dir = a.n, a.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for k in range(n):
        t0 = time.time()
        r = one(k, out_dir, fault_s=a.fault_s, scale=a.scale, frozen_a=a.frozen_a)
        summary.append({"run": k, "class": r["class"], "b_error": r.get("b_error"), "precondition": r.get("precondition"), "wall_s": round(time.time() - t0, 1)})
        (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        print(k, r["class"], r.get("b_error") or r.get("precondition") or "", flush=True)
    from collections import Counter
    print("DIAG_SUMMARY", json.dumps({"n": n, "results": len(summary), **Counter(s["class"] for s in summary)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
