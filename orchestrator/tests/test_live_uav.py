# -*- coding: utf-8 -*-
"""실제 UAV Local Agent(uav/uav-agent, UAV_MODE=mock) 서버와의 HTTP 계약 시험.

실행 전 서버 2대를 띄운다 (저장소 루트의 .venv 기준):
  cd uav/uav-agent
  UAV_ID=A-uav1 UAV_MODE=mock python -m uvicorn main:app --port 8000
  UAV_ID=A-uav2 UAV_MODE=mock python -m uvicorn main:app --port 8001
  ORCH_LIVE_UAV=1 python -m pytest orchestrator/tests/test_live_uav.py -s

PX4/Gazebo 비행이 아니다. UAV 서버의 Mock 비행(배속 100)과 실제 API 형식을 검증한다.
"""

import os
import time

import pytest

from orchestrator.engine import Orchestrator
from orchestrator.env_adapter import FixtureEnv
from orchestrator.knowledge import EnvStationFeed
from orchestrator.ledger import Ledger
from orchestrator.resources import UavClient

pytestmark = pytest.mark.skipif(os.getenv("ORCH_LIVE_UAV") != "1", reason="실제 UAV 서버 필요")

ENDPOINTS = {"A-uav1": "http://127.0.0.1:8000", "A-uav2": "http://127.0.0.1:8001"}
# 복귀 여유 부족 COUNTER(observe_duration_s) 시험용 능선 목표 (uav/uav-agent/README.md 의 관측 목표, 좌표 근사).
#   A 기지가 인제119(environment/config/fire_stations.json)라 배터리 95% 고정이면 이 목표(약 7.8 km)는 ACCEPT 가 된다.
#   COUNTER 가 나오는 배터리 구간은 좁다 (2026-10-16 확인 약 82~84%). 그래서 좌표·배터리 짝에 기대지 않는다:
#   시험이 UAV 자신의 /evaluate 로 COUNTER 가 나오는 배터리 구간을 찾아 그 가운데로 맞춘 뒤 출동시킨다
#   (_calibrate_counter_battery). 항속 반경 안이기만 하면 되고, 배터리 100% 로도 COUNTER 가 안 나오면 원인을 적어 실패한다.
RIDGE = {"lat": 38.0425, "lon": 128.2541, "ground_amsl_m": 804.0, "cell_id": "RIDGE"}
# 인제119 기지에서 약 6 km. 지면고도 400m 는 시험 가정값 (DEM 조회 아님)
NEAR = {"lat": 38.1000, "lon": 128.2150, "ground_amsl_m": 400.0, "cell_id": "NEAR"}


@pytest.fixture(autouse=True)
def idle_drones():
    """앞 시험의 비행이 끝나 착륙할 때까지 기다리고, 배터리를 요청서 §4.2 예시값 95% 로 맞춘다."""
    import httpx
    deadline = time.time() + 90
    for rid, url in ENDPOINTS.items():
        while time.time() < deadline:
            s = httpx.get(f"{url}/uav/{rid}/state", timeout=5).json()
            if s["current_task_id"] is None and not s["armed"]:
                break
            time.sleep(1)
        httpx.post(f"{url}/mock/set", params={"battery_pct": 95}, timeout=5)
    yield


def _env(wind):
    cells = [{**t, "cell_size_m": 90.0, "fire_state": "BURNING"} for t in (RIDGE, NEAR)]
    return FixtureEnv(wind_ms=wind, fire_cells=cells)


def _orch(lg, env):
    # 시험 관측소: 환경 풍속을 목표 근처 관측소 값처럼 전달 (HTTP 계약 시험용)
    return Orchestrator(lg, env, UavClient(ENDPOINTS), weather_feeds=[EnvStationFeed(env, NEAR["lat"], NEAR["lon"])])


def _submit(orch, rid="LIVE-1", target=NEAR):
    task, _ = orch.submit_task({"request_id": rid, "incident_id": "INC-LIVE", "kind": "RECON",
                                "target": dict(target),
                                "requirements": {"resource_types": ["UAV"], "sensor": "THERMAL"}})
    return task


def test_live_normal_recon(tmp_path):
    lg = Ledger(str(tmp_path / "live.db"))
    orch = _orch(lg, _env(3.0))
    task = _submit(orch)
    out = orch.dispatch(task.task_id)
    print("\ndispatch:", out)
    for e in lg.events(task.task_id):
        if e["event_type"] in ("LOCAL_RESPONSE", "SAFETY_JUDGEMENT", "EXECUTION_SENT"):
            print(" ", e["event_type"], e["resource_id"], e["result"], e["reason"])
    assert out["status"] == "STARTED"
    deadline = time.time() + 90
    while time.time() < deadline:
        orch.poll()
        if lg.get_attempt(out["attempt_id"])["substatus"] == "RELEASED":
            break
        time.sleep(1)
    subs = [e["result"] for e in lg.events(task.task_id) if e["event_type"] == "EXECUTION_PROGRESS"]
    print("progress:", subs)
    print("task:", lg.get_task(task.task_id).purpose_status)
    obs = [e for e in lg.events(task.task_id) if e["event_type"] == "OBSERVATION"]
    if obs:
        d = obs[0]["detail"]
        print("observation:", d["result"], "agl", round(d["footprint"]["agl_m"], 1) if d["footprint"] else None,
              "covered", d["target_covered"])
    assert lg.get_task(task.task_id).purpose_status == "COMPLETED"
    assert lg.get_attempt(out["attempt_id"])["substatus"] == "RELEASED"


def _verdict_at(orch, task, battery_pct):
    """두 드론 배터리를 battery_pct 로 맞추고, 출동 때와 같은 평가 요청(Orchestrator._payload)으로 각자의 판정을 받는다."""
    import httpx
    snap = orch.view_for(task)
    out = {}
    for rid, url in ENDPOINTS.items():
        httpx.post(f"{url}/mock/set", params={"battery_pct": battery_pct}, timeout=5).raise_for_status()
        view = orch.uav.state(rid)
        local = orch.uav.evaluate(rid, orch._payload(task, view, snap, "CALIBRATE", task.task_id, {}))
        out[rid] = local
    return out


def _calibrate_counter_battery(orch, task, step=0.01):
    """COUNTER(RETURN_MARGIN_INSUFFICIENT, observe_duration_s) 가 나오는 배터리 구간을 UAV 에게 물어 찾는다.

    UAV 판정은 배터리에 단조롭다: 낮으면 REJECT, 복귀 여유는 모자라도 체류를 줄이면 되면 COUNTER, 넉넉하면 ACCEPT.
    UAV 의 상수(소모율·여유·속도)·기지·DEM 을 시험이 다시 계산하지 않는다 — 이분 탐색으로 구간 양 끝을 찾아 가운데를 쓴다.
    """
    def kind(b):
        res = _verdict_at(orch, task, b)
        vs = {(r["verdict"], r.get("reason"), tuple(sorted((r.get("counter_offer") or {}).keys())))
              for r in res.values()}
        assert len(vs) == 1, f"두 드론 판정이 다르다 (같은 기지·배터리여야 함): {res}"
        v, reason, fields = vs.pop()
        if v == "COUNTER":
            assert (reason, fields) == ("RETURN_MARGIN_INSUFFICIENT", ("observe_duration_s",)), \
                f"예상과 다른 COUNTER: {reason} {fields}"
            return "C"
        if v == "ACCEPT":
            return "A"
        assert reason in ("RETURN_MARGIN_INSUFFICIENT", "LOW_BATTERY"), \
            f"배터리와 무관한 거절 {reason} — 시험 조건(바람·센서·고도)부터 확인: {res}"
        return "R"

    lo, hi = 0.0, 100.0
    k_hi = kind(hi)
    assert k_hi != "R", "배터리 100% 로도 복귀 여유 부족 — 목표가 항속 반경 밖이다 (RIDGE 또는 UAV 기지 확인)"
    if k_hi == "C":
        c = hi
    else:
        c = None
        while hi - lo > step:          # REJECT(lo) / ACCEPT(hi) 사이에서 COUNTER 를 찾는다
            mid = (lo + hi) / 2
            k = kind(mid)
            if k == "C":
                c = mid
                break
            lo, hi = (mid, hi) if k == "R" else (lo, mid)
        assert c is not None, f"COUNTER 구간이 {step}% 보다 좁다 — UAV 가 observe_duration_s COUNTER 를 내지 않는다"
    a, b = lo, c                        # 아래 끝: kind(a) != C, kind(b) == C
    while b - a > step:
        m = (a + b) / 2
        a, b = (a, m) if kind(m) == "C" else (m, b)
    low = b
    a, b = c, hi                        # 위 끝: kind(a) == C, kind(b) != C (hi=100 이 C 면 100 이 위 끝)
    if kind(b) == "C":
        high = b
    else:
        while b - a > step:
            m = (a + b) / 2
            a, b = (m, b) if kind(m) == "C" else (a, m)
        high = a
    target = round((low + high) / 2, 2)
    assert kind(target) == "C"
    return target, (round(low, 2), round(high, 2))


def test_live_ridge_counter_not_executable_holds(tmp_path):
    """요청서 §4.2 예시: 능선 목표는 복귀 여유 부족 COUNTER(observe_duration_s) → 보류.
    총괄이 정한 관측시간보다 짧게 머무르면 관측 목적을 채우지 못하므로 받지 않는다 (config.COUNTER_SUPPORTED_FIELDS).

    배터리는 고정값(95%) 대신 UAV 가 COUNTER 를 내는 구간의 가운데로 맞춘다 (_calibrate_counter_battery).
    출동 직전 같은 요청으로 COUNTER 를 다시 확인해, 구간이 어긋나면 '시험 조건이 틀어졌다'로 실패한다."""
    lg = Ledger(str(tmp_path / "live3.db"))
    orch = _orch(lg, _env(3.0))
    task = _submit(orch, "LIVE-3", RIDGE)
    battery, window = _calibrate_counter_battery(orch, task)
    pre = _verdict_at(orch, task, battery)
    print(f"\nCOUNTER 배터리 구간 {window} → {battery}%:",
          {r: (v["verdict"], v.get("reason"), v.get("counter_offer")) for r, v in pre.items()})
    for rid, v in pre.items():
        assert v["verdict"] == "COUNTER", f"시험 조건 틀어짐: {rid} 가 배터리 {battery}% 에서 {v['verdict']}/{v.get('reason')}"
    out = orch.dispatch(task.task_id)
    print(out)
    assert out["status"] == "HOLD"
    assert set(out["excluded"]) == set(ENDPOINTS)
    assert all(v == "COUNTER_FIELD_UNSUPPORTED:observe_duration_s" for v in out["excluded"].values())


def test_live_high_wind_holds(tmp_path):
    lg = Ledger(str(tmp_path / "live2.db"))
    orch = _orch(lg, _env(12.4))
    out = orch.dispatch(_submit(orch, "LIVE-2").task_id)
    print("\n", out)
    assert out["status"] == "HOLD"
    assert all(v == "LOCAL_REJECT:HIGH_WIND" for v in out["excluded"].values())
