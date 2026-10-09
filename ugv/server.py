# ugv/server.py — UGV Local Agent REST API
#
# 서버 1개가 지상자원 전부(config.RESOURCES)를 맡는다. UAV 는 기체 1대당 서버 1개지만,
# UGV 는 자원들이 도로망 그래프 하나를 공유해야 도로 차단이 모든 판단에 동시에 반영된다.
#
# 실행 (저장소 루트에서):
#   UGV_DRIVER=sim uvicorn ugv.server:app --port 8100          # PX4 없이
#   UGV_DRIVER=px4 uvicorn ugv.server:app --port 8100          # px4_port 가 있는 자원만 PX4, 나머지는 sim
#   UGV_TIME_SCALE=200 UGV_DRIVER=sim uvicorn ugv.server:app --port 8100   # PX4 없이 200배속으로 시나리오 확인
# 문서: http://localhost:8100/docs
#
# 시간: 모든 시각·ETA·속도는 시뮬레이션 초 기준 (ugv/sim_clock.py). 환경 스텝을 POST /clock/env 로 받으면 그에 맞춘다.
# 도로: 차단·혼잡은 시나리오 타임라인(ugv/scenario.py, UGV_SCENARIO — 기본 없음)이 시간대별로 정한다.
#       주행 중 남은 경로가 막히면 지금 달리는 도로 끝에서 다시 탐색해 이어 달린다. 길이 없으면 멈추고 task FAILED.
#
# 호출 순서: state → evaluate → (총괄·Safety 판단) → execute → task 폴링

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import config
from .agent import GroundResourceAgent
from .api_models import (
    CongestionRequest, EvaluateRequest, EvaluateResponse, ExecuteRequest, ExecuteResponse,
    CellsRequest, LatLon, SuppressRequest, TargetNode, TaskStatus, UgvState,
)
from .fleet import GroundFleet
from .geo import distance_m
from . import road_point
from .api_models import StopPoint
from . import graph_gpkg
from .graph_gpkg import ROAD_CELLS
from .road_status import RoadStatus
from .scenario import Scenario
from .sim_clock import SimClock
from .reporter import Reporter
from .history import History
from .gz_fx import fx as gz_fx
from .drive_log import DriveLog, ENABLED as DRIVE_LOG_ENABLED
from .api_models import BlockRequest, EnvClockRequest
from interfaces.exec_store import ExecStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

DRIVER = os.getenv("UGV_DRIVER", "sim").lower()     # "sim" | "px4"
REFRESH_S = 1.0                                     # 텔레메트리 → 자원 상태 반영 주기
CLOCK_FOLLOWS_PX4 = os.getenv("UGV_CLOCK_SOURCE", "px4").lower() == "px4"   # wall 이면 예전처럼 벽시계 × TIME_SCALE
MAX_TARGET_CANDIDATES = 20                          # evaluate: 목표 반경 안에서 시도할 도로 노드 수

fleet: GroundFleet | None = None
roads: RoadStatus | None = None
clock: SimClock | None = None
scenario: Scenario | None = None
reporter: Reporter | None = None
_task_of: dict[str, str | None] = {}                # resource_id → 수행 중 task_id

# 실행 기록 (UGV-02·04): 실행 키 = task_id. 파일에 저장해 재시작 뒤에도 같은 키로 조회·재요청이 같은 결과.
# 재시작으로 끊긴 주행은 FAILED + phase=FAILED 로 닫는다 → 총괄은 FAULTED(점유 유지)로 두고,
# 차가 READY 로 확인될 때 반납한다. 관측(도착) 전 끊김이므로 목적은 다른 자원으로 인계된다.
_STATE_DIR = os.getenv("UGV_STATE_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".state"))
STORE = ExecStore(os.path.join(_STATE_DIR, "ugv_tasks.json"))
_tasks: dict[str, dict] = STORE.tasks                # task_id → TaskStatus 내용
_save = STORE.save


def _close_after_restart(t: dict) -> None:
    t.update({"status": "FAILED", "error": f"AGENT_RESTARTED: 서버 재시작으로 주행 감시가 끊김 (driver={DRIVER})",
              "progress": {**(t.get("progress") or {}), "phase": "FAILED"}})


RESTART_CLOSED = STORE.reconcile_after_restart(
    lambda t: t["status"] in ("STARTED", "IN_PROGRESS"), _close_after_restart,
    basis="SIM_DRIVER_RESET" if DRIVER == "sim" else "PHYSICAL_STATE_FROM_TELEMETRY_AFTER_RESTART")
_watchers: dict[str, asyncio.Task] = {}
road_ai = None                                        # ugv/road_ai.py RoadAI — UGV_AGENT=1 일 때만 (봉인)
history: History | None = None                       # 실행 기록 (lifespan 에서 만든다)             # task_id → 도착 감시 태스크


def _road_snapshot() -> dict:
    active = [] if scenario is None else [
        {k: rule.get(k) for k in ("no", "kind", "targets", "start", "end", "value", "note")}
        for rule in scenario.active(clock.now())]
    return {"blocked": sorted(roads.blocked()), "blocked_by": roads.blocked_by(),
            "blocked_nodes": roads.blocked_nodes(), "congested": roads.congested(), "active_rules": active}


_last_road_snapshot: dict | None = None


def _record_road_state() -> None:
    """막힌 도로·혼잡·켜진 시나리오 규칙이 바뀌었으면 실행 기록에 남긴다 (도로 상황판 재생용)."""
    global _last_road_snapshot
    if history is None:
        return
    snap = _road_snapshot()
    if snap != _last_road_snapshot:
        _last_road_snapshot = snap
        history.record("ROAD_STATE", **snap)


ENV_WAIT_S = 10.0          # 환경 서버를 이만큼(벽시계 초) 못 만나면 시계를 혼자 흐르게 둔다
_env_clock: dict = {"url": None, "run_id": None, "sim_time_s": None, "scenario_start_kst": None, "synced": False}


async def _env_clock_loop() -> None:
    """환경 시계 따라가기 (config.ENV_URL). 환경 시각이 바뀔 때만 UGV 시계를 맞춘다 — 그대로면 손대지 않는다.
    처음 연결하면 환경 시각에 멈춰 둔다(트윈 기동 중 환경은 아직 안 흐른다): 환경이 한 스텝 나아가거나 차가 처음
    출발하면 흐르기 시작한다. 환경이 ENV_WAIT_S 안에 안 뜨면 혼자 흐른다.
    실행이 바뀌거나 시각이 줄면 시나리오를 처음부터. 시나리오 시작 시각이 들어오면 실행 기록에 CLOCK."""
    import httpx
    _env_clock["url"] = config.ENV_URL
    last, t0 = None, time.monotonic()
    async with httpx.AsyncClient(timeout=1.0) as cx:
        while True:
            try:
                h = (await cx.get(f"{config.ENV_URL.rstrip('/')}/health")).json()
                run, t = h.get("run_id"), h.get("simulation_time_s")
                start = (h.get("assumptions") or {}).get("scenario_start_kst")
                if t is not None and (last is None or (run, t) != last):
                    restart = last is not None and (run != last[0] or t < last[1])
                    if last is None and clock.held:
                        clock.hold(float(t))
                        res = {"drift_s": None}
                    else:
                        res = clock.follow_env(float(t))
                    if scenario is not None:
                        if restart:
                            scenario.reset(roads)
                        scenario.tick(clock.now(), roads)
                    if (run, start) != (_env_clock["run_id"], _env_clock["scenario_start_kst"]) and history is not None:
                        history.record("CLOCK", None, None, source="environment", env_run_id=run,
                                       scenario_start_kst=start, env_sim_time_s=t)
                    _env_clock.update(run_id=run, sim_time_s=t, scenario_start_kst=start, synced=True,
                                      drift_s=res["drift_s"])
                    last = (run, t)
            except Exception:   # noqa: BLE001 — 환경이 없으면 혼자 간다
                if last is None and time.monotonic() - t0 > ENV_WAIT_S:
                    clock.release()
            await asyncio.sleep(config.ENV_CLOCK_POLL_S)


async def _refresh_loop() -> None:
    """드라이버 위치·연료를 자원 상태로 옮기고 도착을 확정한다. 시나리오 이벤트도 여기서 적용한다."""
    while True:
        try:
            fleet.refresh_all()
            if scenario is not None:
                scenario.tick(clock.now(), roads)
            _record_road_state()
            gz_fx.sync_walls(roads.blocked())       # Gazebo 빨간 벽 (UGV_GZ_FX=1 일 때만)
        except Exception:
            log.exception("refresh 실패")
        await asyncio.sleep(REFRESH_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global fleet, roads, clock, scenario, reporter, history, road_ai
    clock = SimClock(config.TIME_SCALE, config.SECONDS_PER_ENV_STEP)
    history = History(os.getenv("UGV_HISTORY_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".state", "history")),
                      clock, enabled=os.getenv("UGV_HISTORY", "1") != "0",
                      keep=int(os.getenv("UGV_HISTORY_KEEP", "30")))
    reporter = Reporter(config.REPORT_URL, clock)
    await reporter.start()
    fleet = GroundFleet(use_px4=(DRIVER == "px4"), graph_data=graph_gpkg,   # 실제 도로망
                        time_scale=config.TIME_SCALE)
    roads = RoadStatus(fleet.graph, ROAD_CELLS)
    road_ai = _make_road_ai() if config.AGENT_ENABLED else None
    if config.SCENARIO_FILE:
        scenario = Scenario.load(config.SCENARIO_FILE, config.SECONDS_PER_ENV_STEP)
        scenario.validate(roads)                    # 없는 도로 id 면 여기서 바로 실패
        log.info("시나리오 %s: 규칙 %d개 (%s)", scenario.name, len(scenario.rules), scenario.source)
    await fleet.connect_all()                       # PX4 는 연결될 때까지 대기
    if CLOCK_FOLLOWS_PX4 and any(_driver_kind(a) == "px4" for a in fleet.agents.values()):
        clock.set_source(_px4_time)                 # 시계 흐름 = PX4(Gazebo) 시뮬레이션 시간 (ugv/sim_clock.py)
    history.record("RUN_START", driver=DRIVER, time_scale=config.TIME_SCALE,
                   scenario=None if scenario is None else scenario.name,
                   scenario_source=None if scenario is None else scenario.source,
                   ugv_agent="SEALED" if road_ai is None else f"ON:{road_ai.mode}",
                   resources=[{"resource_id": rid, "resource_type": a.resource.resource_type,
                               "base": a.resource.base, "home_node": a.resource.home_node,
                               "position": {"lat": a.resource.lat, "lon": a.resource.lon},
                               "state": a.resource.state} for rid, a in fleet.agents.items()],
                   bases=_bases())
    _record_road_state()
    loop = asyncio.create_task(_refresh_loop())
    if config.ENV_URL:
        clock.hold(0.0)                             # 환경 시계를 받을 때까지 (또는 첫 출발까지) 멈춰 둔다
    env_loop = asyncio.create_task(_env_clock_loop()) if config.ENV_URL else None
    log.info("UGV 서버 준비: driver=%s, 자원 %s, 시간배율 %.0f, 환경 1스텝=%.0fs", DRIVER, list(fleet.agents),
             config.TIME_SCALE, config.SECONDS_PER_ENV_STEP)
    yield
    loop.cancel()
    if env_loop:
        env_loop.cancel()
    await reporter.stop()
    history.close()


app = FastAPI(
    title="UGV Local Agent",
    description="산불 대응 시뮬레이터 — 지상자원(UGV·소방차) 상태 제공, 도로망 기반 수행 가능성 판단, 주행",
    version="0.1.0",
    lifespan=lifespan,
)


def _agent(resource_id: str) -> GroundResourceAgent:
    """없는 자원이면 404. 조용히 다른 자원 값을 주는 것보다 끊는 쪽이 안전하다."""
    agent = fleet.agents.get(resource_id)
    if agent is None:
        raise HTTPException(404, f"자원 {resource_id} 없음. 담당 자원: {list(fleet.agents)}")
    return agent


def _report(type_: str, agent: GroundResourceAgent, task_id: str | None = None, **payload) -> None:
    """총괄 보고 (ugv/reporter.py). 위치·상태를 항상 같이 싣는다."""
    r = agent.resource
    reporter.report(type_, r.resource_id, task_id, state=r.state,
                    position={"lat": r.lat, "lon": r.lon}, fuel_pct=r.fuel_pct, **payload)
    if history is not None:
        history.record(type_, r.resource_id, task_id, state=r.state,
                       position={"lat": r.lat, "lon": r.lon}, **payload)
        if type_ in ("UGV_TASK_STARTED", "UGV_REROUTED") and agent.plan is not None:
            history.record("ROUTE", r.resource_id, task_id, target_node=agent.plan.target_node,
                           path=agent.plan.path, legs=_route_legs(agent), why=type_)


def _resource_changed(agent: GroundResourceAgent, why: str) -> None:
    """자원 상태가 바뀌었다 (READY 복귀·UNAVAILABLE). 총괄은 이걸 받으면 보류 임무를 다시 배정한다."""
    _report("RESOURCE_CHANGED", agent, None, resource_type=agent.resource.resource_type,
            current_node=agent.resource.current_node, fault=agent.fault, why=why)


def _driver_kind(agent: GroundResourceAgent) -> str:
    return "px4" if type(agent.driver).__name__ == "PX4Driver" else "sim"


def _px4_time():
    """시계 소스: PX4 차량 중 시각이 들어오는 첫 차의 imu 시각. 모두 같은 Gazebo 라 흐름이 같다."""
    for rid, agent in fleet.agents.items():
        if _driver_kind(agent) == "px4":
            t = agent.driver.telemetry().get("px4_time_s")
            if t:
                return f"px4:{rid}", t
    return None


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "driver": DRIVER,
        "resources": {rid: _driver_kind(a) for rid, a in fleet.agents.items()},
        "graph": {"nodes": len(fleet.graph._nodes), "roads": len(fleet.graph._roads)},
        "approach": {"target_snap_m": config.TARGET_SNAP_M, "fallback": config.APPROACH_FALLBACK,
                     "approach_max_m": config.APPROACH_MAX_M},
        "clock": clock.info(),
        "scenario": scenario.name if scenario else None,
        "max_speed_mps": {rid: a.max_speed_mps for rid, a in fleet.agents.items()},
    }


def _state(agent: GroundResourceAgent) -> UgvState:
    agent.refresh()
    r = agent.resource
    return UgvState(
        resource_id=r.resource_id,
        resource_type=r.resource_type,
        base=r.base,
        state=r.state,
        position=LatLon(lat=r.lat, lon=r.lon),
        fuel_pct=r.fuel_pct,
        current_node=r.current_node,
        current_task_id=_task_of.get(r.resource_id),
        driver=_driver_kind(agent),
        driver_status=agent.driver.status() if agent.driver else "NONE",
        updated_at=r.updated_at,
        fault=agent.fault,
        current_road_id=agent.current_road_id(),
        sim_time_s=round(clock.now(), 1),
        activity=None if r.equipment is None else r.equipment.activity,
        equipment=None if r.equipment is None else r.equipment.to_dict(),
    )


@app.get("/ugv", response_model=list[UgvState])
async def list_state(base: str | None = None):
    """거점별 자원 목록. 총괄의 get_ugv_status(base) 에 대응한다."""
    return [_state(a) for a in fleet.agents.values() if base is None or a.resource.base == base]


@app.get("/ugv/{resource_id}/state", response_model=UgvState)
async def get_state(resource_id: str):
    return _state(_agent(resource_id))


def _decide(agent: GroundResourceAgent, target: LatLon | None, target_node: str | None,
            cargo=None, via_node: str | None = None, target_mode: str | None = None) -> dict:
    """목적지 도로 노드를 고르고 갈 수 있는지 판단한다. evaluate·execute 가 같은 규칙을 쓴다.

    target(화재 좌표)을 주면 화재에서 가장 가까운 도로 노드를 목적지로 삼는다.
      - 그 노드가 TARGET_SNAP_M 보다 멀면 TARGET_UNREACHABLE
      - 그 노드로 못 가면 기본은 REJECT. APPROACH_FALLBACK=1 이면 화재에서
        APPROACH_MAX_M 안의 다음 노드들을 가까운 순으로 시도한다 (ugv/config.py)
    cargo(짐)가 있으면 적재 한도를 먼저 보고, via_node(싣는 곳)가 있으면 지금 → 경유지 → 목적지로 판단한다.
    ETA 에는 싣기 시간(LOAD_S)이 들어간다. 내리기는 도착 뒤 작업이라 ETA 에 넣지 않는다.
    target_mode="road_point"(또는 UGV_TARGET_MODE) 이고 target 을 주면 노드 대신 가장 가까운 도로 위 점에 선다
    (ugv/road_point.py). 짐 싣기(cargo)와는 같이 쓰지 않는다.
    반환: verdict, eta_sec, reason, detail, target_node(TargetNode|None), path, stop_point(StopPoint|None), at_target
    """
    rid = agent.resource.resource_id

    def reject(reason, detail, tn=None, sp=None):
        return dict(verdict="REJECT", eta_sec=None, reason=reason, detail=detail, target_node=tn, path=None,
                    stop_point=sp, at_target=False)

    # 총괄은 평가에서 받은 target_node 를 실행 때 target 과 같이 돌려보낸다 (engine._approve_and_send) —
    # 도로 위 지점 방식이면 target 기준으로 다시 고른다 (평가와 같은 규칙이라 같은 끝 노드·지점이 나온다)
    if target is not None and cargo is None and (target_mode or config.TARGET_MODE) == "road_point":
        return _decide_point(agent, target, reject)

    if cargo is not None:
        eq = agent.resource.equipment
        why = "장비 정보 없음" if eq is None else eq.can_carry(cargo.kg)
        if why:
            return reject("REQUIRED_CAPABILITY_UNAVAILABLE", why)
    if via_node is not None:
        if cargo is None:
            raise HTTPException(422, "via_node 는 cargo 와 같이 쓴다 (짐 싣는 곳)")
        try:
            fleet.graph.node(via_node)
        except KeyError:
            raise HTTPException(404, f"경유 노드 {via_node} 없음")

    def judge(node_id: str) -> dict:
        """agent.evaluate 와 같은 형식. 짐이 있으면 경유지·싣기 시간을 넣는다."""
        if via_node is None:
            res = agent.evaluate(node_id)
            if res["response"] == "ACCEPT" and cargo is not None:
                res = {**res, "eta_s": res["eta_s"] + config.LOAD_S}
            return res
        first = agent.evaluate(via_node)
        if first["response"] != "ACCEPT":
            return first
        second = fleet.graph.find_route(via_node, node_id, agent.max_speed_mps)
        if not second.reachable:
            return {"resource_id": rid, "response": "REJECT", "blocked_road_id": second.blocked_road_id,
                    "reason": "ROAD_BLOCKED" if second.blocked_road_id else "TARGET_UNREACHABLE"}
        return {"resource_id": rid, "response": "ACCEPT", "eta_s": first["eta_s"] + config.LOAD_S + second.eta_s,
                "path": first["path"] + second.path[1:]}

    if target_node is not None:
        try:
            n = fleet.graph.node(target_node)
        except KeyError:
            raise HTTPException(404, f"도로 노드 {target_node} 없음")
        candidates = [(n, 0.0)]
    elif target is not None:
        nearest, d = fleet.graph.nearest_node(target.lat, target.lon)
        if d > config.TARGET_SNAP_M:
            return reject("TARGET_UNREACHABLE",
                          f"가장 가까운 도로 노드가 {d:.0f} m 떨어짐 (허용 {config.TARGET_SNAP_M:.0f} m)")
        candidates = [(nearest, d)]
        if config.APPROACH_FALLBACK:   # 가장 가까운 노드로 못 가면 반경 안 다음 노드로
            candidates += [c for c in fleet.graph.nodes_within(target.lat, target.lon, config.APPROACH_MAX_M)
                           if c[0].node_id != nearest.node_id][:MAX_TARGET_CANDIDATES - 1]
    else:
        raise HTTPException(422, "target 또는 target_node 중 하나가 필요하다")

    first_reject = None
    for node, snap_m in candidates:
        tn = TargetNode(node_id=node.node_id, lat=node.lat, lon=node.lon, snap_m=round(snap_m, 1))
        result = judge(node.node_id)
        if result["response"] == "ACCEPT":
            return dict(verdict="ACCEPT", eta_sec=round(result["eta_s"]), reason=None,
                        detail=None if first_reject is None else f"가장 가까운 노드는 도달 불가, {snap_m:.0f} m 지점으로 접근",
                        target_node=tn, path=result["path"], stop_point=None, at_target=len(result["path"]) == 1)
        if result["reason"] == "BUSY":
            return reject("BUSY", f"수행 중 task {_task_of.get(rid)}")
        if result.get("fault"):                 # UNAVAILABLE — 주행 중 이상, /stop 으로 해제
            return reject(result["reason"], f"자원 이상 [{result['fault']}] — 확인 후 /stop 으로 복귀")
        first_reject = first_reject or (result, tn)

    result, tn = first_reject
    blocked = result.get("blocked_road_id")
    return reject(result["reason"],
                  (f"후보 노드 {len(candidates)}개 모두 도달 불가" if len(candidates) > 1
                   else f"화재에서 가장 가까운 노드 {tn.node_id}({tn.snap_m:.0f} m) 도달 불가")
                  + (f", 차단 도로 {blocked}" if blocked else ""), tn)


def _decide_point(agent: GroundResourceAgent, target: LatLon, reject) -> dict:
    """도로 위 지점 목적지. 이미 그 지점(NODE_ARRIVE_M 안)에 서 있으면 움직이지 않고 도착 (붙박이 반복 관측)."""
    rp = road_point.nearest(fleet.graph, target.lat, target.lon)
    if rp is None or rp.snap_m > config.TARGET_SNAP_M:
        return reject("TARGET_UNREACHABLE", "가까운 도로 없음" if rp is None else
                      f"가장 가까운 도로가 {rp.snap_m:.0f} m 떨어짐 (허용 {config.TARGET_SNAP_M:.0f} m)")
    sp = StopPoint(**rp.to_dict())
    r = agent.resource
    if r.state == "READY" and r.current_node is not None \
            and distance_m((r.lat, r.lon), (rp.lat, rp.lon)) <= config.NODE_ARRIVE_M:
        n = fleet.graph.node(r.current_node)
        return dict(verdict="ACCEPT", eta_sec=0, reason=None, detail="이미 그 지점에 서 있다",
                    target_node=TargetNode(node_id=n.node_id, lat=n.lat, lon=n.lon, snap_m=round(rp.snap_m, 1)),
                    path=[n.node_id], stop_point=sp, at_target=True)
    res = agent.evaluate_point(rp)
    if res is None or res["response"] != "ACCEPT":
        res = res or {}
        if res.get("reason") == "BUSY":
            return reject("BUSY", f"수행 중 task {_task_of.get(agent.resource.resource_id)}", sp=sp)
        if res.get("fault"):
            return reject(res["reason"], f"자원 이상 [{res['fault']}] — 확인 후 /stop 으로 복귀", sp=sp)
        blocked = res.get("blocked_road_id")
        return reject(res.get("reason") or "TARGET_UNREACHABLE",
                      f"도로 {rp.road_id} 위 지점 도달 불가" + (f", 차단 도로 {blocked}" if blocked else ""), sp=sp)
    n = fleet.graph.node(res["end_node"])
    return dict(verdict="ACCEPT", eta_sec=round(res["eta_s"]), reason=None,
                detail=f"도로 {rp.road_id} 위 지점 (도로에서 {rp.snap_m:.0f} m)",
                target_node=TargetNode(node_id=n.node_id, lat=n.lat, lon=n.lon, snap_m=round(rp.snap_m, 1)),
                path=res["path"], stop_point=sp, at_target=False)


def _rp(sp: StopPoint | None):
    return None if sp is None else road_point.RoadPoint(sp.road_id, sp.lat, sp.lon, sp.snap_m, sp.along_m)


@app.post("/ugv/{resource_id}/evaluate", response_model=EvaluateResponse)
async def evaluate(resource_id: str, req: EvaluateRequest):
    """수행 가능성 판단. 차를 움직이지 않는다. 목적지 선정 규칙은 _decide 참고."""
    agent = _agent(resource_id)
    d = _decide(agent, req.target, req.target_node, req.cargo, req.via_node, req.target_mode)
    sp = d["stop_point"]
    _report("UGV_EVALUATED", agent, req.task_id, decision_id=req.decision_id, verdict=d["verdict"],
            eta_sec=d["eta_sec"], reason=d["reason"], detail=d["detail"],
            target_node=None if d["target_node"] is None else d["target_node"].node_id,
            **({} if sp is None else {"stop_point": sp.model_dump()}))
    return EvaluateResponse(task_id=req.task_id, decision_id=req.decision_id, resource_id=resource_id,
                            **{k: v for k, v in d.items() if k != "at_target"})


@app.get("/ugv/{resource_id}/observation")
async def observation(resource_id: str):
    """현재 위치의 도로 상태 관측. 공통 Observation 필드 이름을 따른다 (simulation_time_s 는 호출측이 붙인다)."""
    agent = _agent(resource_id)
    agent.refresh()
    r = agent.resource
    return {
        "resource_id": r.resource_id,
        "location_lat": r.lat,
        "location_lon": r.lon,
        "observation_type": "ROAD_STATUS",
        "value": {"state": r.state, "current_node": r.current_node,
                  "current_task_id": _task_of.get(resource_id),
                  "blocked_roads": len(roads.blocked()), "blocked_nodes": len(roads.blocked_nodes())},
    }


@app.get("/graph/nodes/{node_id}")
async def get_node(node_id: str):
    """도로 노드 좌표 조회 (총괄 GroundAdapter.position_of_node 대응)."""
    try:
        n = fleet.graph.node(node_id)
    except KeyError:
        raise HTTPException(404, f"도로 노드 {node_id} 없음")
    return {"node_id": n.node_id, "lat": n.lat, "lon": n.lon, "name": n.name}


# --- 실행 -------------------------------------------------------------------

def _remaining(agent: GroundResourceAgent, passed: int) -> dict:
    """남은 거리·시간(시뮬레이션 초)·지금 달리는 도로. 웨이포인트 단위 근사."""
    plan = agent.plan
    if plan is None or not plan.waypoints:
        return {}
    here = (agent.resource.lat, agent.resource.lon)
    pts = [here] + plan.waypoints[passed:]
    spd = plan.speeds[passed:]
    dist = [distance_m(a, b) for a, b in zip(pts, pts[1:])]
    return {"remaining_m": round(sum(dist)),
            "eta_remaining_sec": round(sum(d / v for d, v in zip(dist, spd))),
            "current_road_id": agent.current_road_id(),
            "sim_time_s": round(clock.now(), 1)}


def _check_run(agent: GroundResourceAgent, w: dict, now: float) -> str | None:
    """주행 감시 1회. 이상이 확정되면 'CODE: 설명', 아니면 None.
    now 는 시뮬레이션 초(멈춤 판정 — 차가 시뮬레이션 안에서 못 움직인 시간), 차량 이상의 유예·확정은
    통신·모드 전환 시간이라 벽시계(w 의 started·fault_since, time.monotonic)로 잰다.
    w: task 별 감시 상태 (started, mark_t, mark_pos, mark_wp, fault_since)."""
    r, (cur, _) = agent.resource, agent.driver.progress()
    pos = (r.lat, r.lon)

    # 1) 멈춤 — STALL_MOVE_M 이상 움직이거나 웨이포인트를 넘기면 기준점을 새로 잡는다
    #    마지막 웨이포인트에 닿은 차(cur >= total)는 도착해 서 있는 것이지 멈춘 것이 아니다.
    total = agent.driver.progress()[1]
    if total > 0 and cur >= total:
        w.update(mark_t=now, mark_pos=pos, mark_wp=cur)
    elif cur != w["mark_wp"] or distance_m(pos, w["mark_pos"]) >= config.STALL_MOVE_M:
        w.update(mark_t=now, mark_pos=pos, mark_wp=cur)
    elif now - w["mark_t"] > config.STALL_TIMEOUT_S:
        return (f"STALLED: {config.STALL_TIMEOUT_S:.0f}초간 이동 "
                f"{distance_m(pos, w['mark_pos']):.0f} m, 웨이포인트 {cur} 에서 멈춤")

    # 2) 경로 이탈
    off = agent.off_route_m()
    if off > config.OFF_ROUTE_M:
        return f"OFF_ROUTE: 경로에서 {off:.0f} m 벗어남 (허용 {config.OFF_ROUTE_M:.0f} m)"

    # 3) 차량 이상 (드라이버가 판정) — 출발 직후 유예, 일정 시간 계속될 때만 확정
    wall = time.monotonic()
    fault = agent.driver.fault() if wall - w["started"] > config.FAULT_GRACE_S else None
    if fault is None:
        w["fault_since"] = None
    elif w["fault_since"] is None:
        w["fault_since"] = wall
    elif wall - w["fault_since"] >= config.FAULT_CONFIRM_S:
        return fault
    return None


# --- 실행 단계 ---------------------------------------------------------------
# task 하나 = 단계 목록. ("DRIVE", 노드) 는 그 노드까지 주행, ("LOAD", None) 은 지금 자리에서 짐 싣기.
#   목적지만:          [DRIVE 목적지]
#   짐, 경유지 없음:    [LOAD, DRIVE 목적지]
#   짐 + 경유지:        [DRIVE 경유지, LOAD, DRIVE 목적지]
# 마지막 DRIVE 도착 = task COMPLETED (계약 그대로). 그 뒤 작업(진압·짐 내리기)은 _work 가 따로 돈다 —
# 그동안 차는 state=WORKING 이라 총괄이 반납하지 않는다.

def _stages(target_node: str, via_node: str | None, cargo) -> list[tuple[str, str | None]]:
    if cargo is None:
        return [("DRIVE", target_node)]
    if via_node:
        return [("DRIVE", via_node), ("LOAD", None), ("DRIVE", target_node)]
    return [("LOAD", None), ("DRIVE", target_node)]


async def _sim_sleep_until(until_s: float) -> None:
    """시뮬레이션 초 until_s 까지 기다린다 (Gazebo 가 느려지면 같이 느려진다 — ugv/sim_clock.py)."""
    while clock.now() < until_s:
        await asyncio.sleep(0.5)


def _fail_task(agent, task_id: str, t: dict, reason: str, error: str, why: str, progress: dict) -> None:
    t["status"], t["error"] = "FAILED", error
    t["progress"] = {"phase": "FAILED", **progress}
    log.warning("task %s 실패 — %s", task_id, error)
    _report("UGV_TASK_FAILED", agent, task_id, reason=reason, error=error)
    _resource_changed(agent, why)


async def _drive_leg(task_id: str, agent: GroundResourceAgent, node: str, dlog, stage: str) -> bool:
    """한 구간 주행을 지켜본다. 도착하면 True, 실패(차단·이상)면 task 를 FAILED 로 적고 False.

    이상(_check_run)이 나면 차를 세우고 자원을 UNAVAILABLE 로 둔다.
    떨어지거나 고장 난 차가 곧바로 READY 가 되면 총괄이 또 배정하므로, 운영자가 /stop 으로 풀어야 한다.
    """
    t = _tasks[task_id]
    w = dict(started=time.monotonic(), mark_t=clock.now(), mark_pos=(agent.resource.lat, agent.resource.lon),
             mark_wp=0, fault_since=None)
    last_road = None
    while True:
        agent.refresh()
        agent.check_arrival()
        cur, total = agent.driver.progress()
        prev = t.get("progress") or {}
        changed = t["status"] != "IN_PROGRESS" or (prev.get("phase"), prev.get("waypoint"), prev.get("total"),
                                                  prev.get("stage")) != ("ENROUTE", cur, total, stage)
        t["status"] = "IN_PROGRESS"
        t["progress"] = {"phase": "ENROUTE", "stage": stage, "leg_target": node, "waypoint": cur, "total": total,
                         **_remaining(agent, cur)}
        if dlog:
            dlog.sample(t["progress"])
        if changed:                         # 파일 저장은 웨이포인트가 바뀔 때만 (남은 거리·시각은 매번 바뀐다)
            _save()
        if agent.resource.state == "READY" and agent.resource.current_node == node:
            return True
        if total > 0 and cur >= total and agent.resource.state not in ("RUNNING", "UNAVAILABLE"):
            # 마지막 웨이포인트에 닿았는데 다른 경로로 READY 가 아닌 상태(WORKING 등)가 됐다 — 도착으로 본다.
            # (이걸 놓치면 서 있는 차를 멈춤 감시가 STALLED 로 잡아 UNAVAILABLE 로 만든다)
            agent.resource.current_node = node
            return True
        road = t["progress"].get("current_road_id")
        if road and road != last_road:          # 진행 보고는 도로가 바뀔 때마다 한 번
            last_road = road
            _report("UGV_PROGRESS", agent, task_id, **t["progress"])
        if agent.resource.state == "RUNNING" and agent.blocked_ahead():
            res = (await _ai_detour(task_id, agent, t) if road_ai is not None and _driver_kind(agent) == "sim"
                   else await agent.reroute())
            t.setdefault("reroutes", []).append({"sim_time_s": round(clock.now(), 1), **res,
                                                 "eta_s": None if res["eta_s"] is None else round(res["eta_s"])})
            if res["result"] == "NO_ROUTE":
                await agent.stop()          # 멈춘 곳에서 가장 가까운 노드에 READY — 고장이 아니므로 UNAVAILABLE 아님
                _fail_task(agent, task_id, t, "ROAD_BLOCKED",
                           f"ROAD_BLOCKED: 주행 중 {res['blocked_road_id']} 차단, 우회 경로 없음",
                           "TASK_FAILED_ROAD_BLOCKED", {"waypoint": cur, "total": total})
                return False
            log.info("task %s 재탐색 — %s 차단, 남은 ETA %.0fs", task_id, res["blocked_road_id"], res["eta_s"])
            _report("UGV_REROUTED", agent, task_id, blocked_road_id=res["blocked_road_id"],
                    eta_remaining_sec=round(res["eta_s"]), reroutes=agent.reroutes,
                    **({"ai": res["ai"]} if res.get("ai") else {}))
            w.update(mark_t=clock.now(), mark_wp=-1)
            continue
        fault = _check_run(agent, w, clock.now())
        if fault:
            await agent.fail(fault)
            _fail_task(agent, task_id, t, fault.split(":")[0], fault, "FAULT", {"waypoint": cur, "total": total})
            return False
        await asyncio.sleep(0.5)


# --- 도로 AI (ugv/road_ai.py, 봉인) --------------------------------------------

def _make_road_ai():
    from . import road_ai as ra
    from .road_news import RoadNews
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from pathlib import Path
    ra.load_env_keys(Path(root) / ".env")
    client = ra.GeminiClient(os.getenv("UGV_AGENT_API_KEY"), config.AGENT_MODEL, config.AGENT_EMBED_MODEL,
                             config.AGENT_BASE_URL, config.AGENT_TIMEOUT_S)
    news_path = config.AGENT_NEWS if os.path.isabs(config.AGENT_NEWS) else os.path.join(root, config.AGENT_NEWS)
    news = RoadNews.load(news_path, config.SECONDS_PER_ENV_STEP,
                         embed=client.embed if (config.AGENT_EMBED and client.key) else None)
    ai = ra.RoadAI(client, news, config.AGENT_MODE, config.AGENT_MAX_CALLS)
    log.info("도로 AI 켜짐: %s, 모델 %s, 기사 %d건%s", ai.mode, client.model, len(news.articles),
             "" if client.key else " — 키 없음(UGV_AGENT_API_KEY), 판단은 규칙(1순위 우회)으로")
    return ai


def _start_kst() -> str | None:
    """시뮬레이션 0초의 실제 시각: 환경 서버 값, 없으면 도로 AI 기사 묶음의 scenario_start_kst (기사 본문 시각과 맞춘다)."""
    return _env_clock.get("scenario_start_kst") or (getattr(road_ai.news, "start_kst", None) if road_ai else None)


def _kst(sim_s: float) -> str:
    """시뮬레이션 초 → 'HH:MM' (시작 시각을 알면 실제 시각, 모르면 시뮬레이션 시:분)."""
    from datetime import datetime, timedelta
    start = _start_kst()
    if start:
        try:
            return (datetime.fromisoformat(start) + timedelta(seconds=sim_s)).strftime("%H:%M")
        except ValueError:
            pass
    return f"{int(sim_s) // 3600:02d}:{int(sim_s) % 3600 // 60:02d}"


def _from_kst(text: str) -> float:
    """'HH:MM' → 시뮬레이션 초 (_kst 의 반대). 시작 시각보다 이르면 다음 날로 본다."""
    from datetime import datetime, timedelta
    h, m = (int(x) for x in text.strip().split(":")[:2])
    start = _start_kst()
    if start:
        try:
            st = datetime.fromisoformat(start)
            t = st.replace(hour=h, minute=m, second=0, microsecond=0)
            if t < st:
                t += timedelta(days=1)
            return (t - st).total_seconds()
        except ValueError:
            pass
    return h * 3600 + m * 60


async def _ai_detour(task_id: str, agent: GroundResourceAgent, t: dict) -> dict:
    """앞길이 막혔다 — 차를 세우고 도로 AI 에 우회(1·2순위)·대기를 묻고 그대로 따른다. 반환은 agent.reroute 와 같은
    모양 + ai(결정 요약). AI 가 못 쓰이면(키·한도·오류) 1순위 우회 = AI 를 끈 때와 같다."""
    from . import route_alt
    from .road_ai import RoadAI
    blocked = agent.blocked_ahead()
    cur, _ = agent.driver.progress()
    eta_before = (_remaining(agent, cur).get("eta_remaining_sec") or 0)
    await agent.pause()
    t["progress"] = {**(t.get("progress") or {}), "phase": "DECIDING", "blocked_road_id": blocked}
    _save()
    start_node, lead, here = agent.detour_start()
    lead_s = sum(l["distance_m"] / l["speed_mps"] for l in lead)
    target = agent._target_node
    best, alt = await asyncio.to_thread(route_alt.best_and_alternative, fleet.graph, start_node, target,
                                        agent.max_speed_mps)
    if best is None:                               # 우회로가 아예 없다 — AI 없이 하던 대로 (실패 처리)
        return await agent.reroute()
    tail_s = agent.tail_s(target)

    def opt(name, o):
        names = []
        for r in o.roads:
            n = fleet.graph.get_road(r).name or r
            if not names or names[-1] != n:
                names.append(n)
        return {"name": name, "eta_s": lead_s + o.travel_s + tail_s, "distance_m": o.distance_m,
                "road_ids": o.roads, "road_names": names, "path": o.path}

    options = [opt("ROUTE_1", best)] + ([opt("ROUTE_2", alt)] if alt else [])
    r = agent.resource
    now = clock.now()
    s = {"now_s": now, "now_text": _kst(now), "resource_id": r.resource_id, "resource_type": r.resource_type,
         "target": _node_name(target) or target, "blocked_road_id": blocked,
         "blocked_name": fleet.graph.get_road(blocked).name or blocked,
         "here_name": fleet.graph.get_road(lead[0]["road_id"]).name or lead[0]["road_id"],
         "eta_before_s": eta_before, "options": options, "to_sim": _from_kst}
    if history is not None:
        history.record("AGENT_REQUEST", r.resource_id, task_id, roads=[blocked], mode=road_ai.mode,
                       model=road_ai.client.model, prompt=RoadAI.situation_text(s),
                       options=[{k: o[k] for k in ("name", "eta_s", "distance_m", "road_ids")} for o in options])
    res = await asyncio.to_thread(road_ai.decide, s)
    for e in res["trace"]:
        if e["type"] == "AGENT_REQUEST" or history is None:
            continue
        data = {k: v for k, v in e.items() if k != "type"}
        if e["type"] == "AGENT_DECISION":
            chosen = next((o for o in options if o["name"] == res["decision"]), None)
            data["roads"] = chosen["road_ids"] if chosen else [blocked]
        history.record(e["type"], r.resource_id, task_id, **data)
    ai = {k: res.get(k) for k in ("decision", "reason", "article_ids", "mode", "fallback", "latency_s")}
    log.info("task %s 도로 AI: %s (%s)%s", task_id, res["decision"], res["reason"][:80],
             f" — fallback {res['fallback']}" if res.get("fallback") else "")
    if res["decision"] == "WAIT":
        until = min(res["wait_until_s"], clock.now() + config.AGENT_MAX_WAIT_S)
        ai["wait_until_s"] = round(until, 1)
        t["progress"] = {**(t.get("progress") or {}), "phase": "WAITING", "blocked_road_id": blocked,
                         "wait_until_sim_s": round(until, 1)}
        _save()
        _report("UGV_WAITING", agent, task_id, blocked_road_id=blocked, wait_until_sim_s=round(until, 1),
                reason=res["reason"])
        while clock.now() < until and fleet.graph.get_road(blocked).blocked:
            await asyncio.sleep(0.5)
        ai["waited_s"] = round(clock.now() - now, 1)
        ai["reopened"] = not fleet.graph.get_road(blocked).blocked
        out = await agent.reroute()                 # 열렸으면 원래 길, 아니면 1순위 우회
    elif res["decision"] == "ROUTE_2" and alt is not None:
        out = await agent.reroute(path=alt.path)
        if out["result"] == "NO_ROUTE":            # 그 사이 2순위도 막혔다
            ai["fallback"] = "ROUTE_2_BLOCKED"
            out = await agent.reroute()
    else:
        out = await agent.reroute()
    out["blocked_road_id"] = out.get("blocked_road_id") or blocked
    out["ai"] = ai
    return out


async def _load(task_id: str, agent: GroundResourceAgent, stage: str) -> None:
    """지금 자리에서 짐 싣기 (LOAD_S 시뮬레이션 초). 그동안 state=WORKING."""
    t, r = _tasks[task_id], agent.resource
    eq, now = r.equipment, clock.now()
    r.state = "WORKING"
    eq.begin("LOADING", task_id, now, now + config.LOAD_S)
    t["status"] = "IN_PROGRESS"
    t["progress"] = {"phase": "LOADING", "stage": stage, "until_sim_s": round(now + config.LOAD_S, 1)}
    _save()
    _report("UGV_LOADING", agent, task_id, cargo=t.get("cargo"), node=r.current_node)
    try:
        await _sim_sleep_until(now + config.LOAD_S)
    finally:
        eq.end(clock.now(), "DONE", cargo=t.get("cargo"))
        if r.state == "WORKING":
            r.state = "READY"
    eq.cargo = {**t["cargo"], "loaded": True}
    t["cargo"]["loaded_sim_s"] = round(clock.now(), 1)
    gz_fx.cargo(r.resource_id, True)
    _save()


async def _run_task(task_id: str, agent: GroundResourceAgent, stages: list, eta_sec: float | None = None) -> None:
    """단계를 차례로 수행한다. 마지막 DRIVE 도착 → COMPLETED + 도착 뒤 작업 시작. 실패면 FAILED."""
    rid = agent.resource.resource_id
    t = _tasks[task_id]
    target_node = stages[-1][1]
    dlog = DriveLog(_STATE_DIR, task_id, agent, clock) if DRIVE_LOG_ENABLED else None
    if dlog:
        rel = os.path.relpath(dlog.path)
        t["drive_log"] = dlog.path if rel.startswith("..") else rel
    try:
        for i, (kind, node) in enumerate(stages):
            stage = f"{i + 1}/{len(stages)}"
            if kind == "LOAD":
                await _load(task_id, agent, stage)
                continue
            if i > 0:                          # 첫 주행은 execute 가 이미 시작했다
                if not await agent.execute(node):
                    res = agent.evaluate(node)
                    _fail_task(agent, task_id, t, res.get("reason") or "TARGET_UNREACHABLE",
                               f"{res.get('reason')}: 다음 구간({node}) 출발 불가", "TASK_FAILED", {"stage": stage})
                    return
                _siren(agent, True)
            if not await _drive_leg(task_id, agent, node, dlog, stage):
                _siren(agent, False)
                return
        r = agent.resource
        t["status"] = "COMPLETED"
        cur, total = agent.driver.progress()
        t["progress"] = {"phase": "ARRIVED", "stage": f"{len(stages)}/{len(stages)}", "waypoint": total, "total": total}
        # 지상자원 관측은 도로 상태다. 도착했다고 화재를 관측한 것은 아니다.
        t["observation"] = {
            "observation_type": "ROAD_STATUS",
            "arrived_node": target_node,
            "position": {"lat": r.lat, "lon": r.lon},
            "fuel_pct": r.fuel_pct,
        }
        _report("UGV_ARRIVED", agent, task_id, target_node=target_node, observation=t["observation"],
                reroutes=len(t.get("reroutes") or []),
                **({"stop_point": t["stop_point"]} if t.get("stop_point") else {}))
        _after_arrival(agent, task_id)
        if agent.resource.state == "READY":
            _resource_changed(agent, "ARRIVED")
    except asyncio.CancelledError:
        pass                                  # /stop 이 상태를 CANCELLED 로 기록한다
    except Exception as e:   # noqa: BLE001
        t["status"], t["error"] = "FAILED", str(e)
        log.exception("task %s 실패", task_id)
        _report("UGV_TASK_FAILED", agent, task_id, reason="INTERNAL_ERROR", error=str(e))
    finally:
        if dlog:
            dlog.sample(t.get("progress") or {}, force=True)
            t["timing"] = dlog.close(eta_sec)
        _save()
        if _task_of.get(rid) == task_id:      # 정지 직후 새 임무가 들어왔으면 그 연결은 지우지 않는다
            _task_of[rid] = None
        _watchers.pop(task_id, None)


# --- 도착 뒤 작업 (진압·짐 내리기) ---------------------------------------------
_works: dict[str, asyncio.Task] = {}                 # resource_id → 작업 태스크


def _siren(agent: GroundResourceAgent, on: bool) -> None:
    eq = agent.resource.equipment
    if eq is not None and eq.has_siren and eq.siren_on != on:
        eq.siren_on = on
        gz_fx.siren(agent.resource.resource_id, on)


def _after_arrival(agent: GroundResourceAgent, task_id: str) -> None:
    """도착한 곳에 따라: 거점이면 물 채우기, 짐이 있으면 내리기, 소방차면 진압 (AUTO_SUPPRESS)."""
    r = agent.resource
    eq = r.equipment
    if eq is None:
        return
    if r.current_node == r.home_node and eq.water_capacity_l:
        added = eq.refill()
        if added:
            _report("UGV_REFILLED", agent, task_id, water_l=eq.water_l, added_l=round(added, 1))
    if eq.cargo and eq.cargo.get("loaded"):
        _start_work(agent, "UNLOADING", task_id, until_s=clock.now() + config.UNLOAD_S)
    elif r.resource_type == "FIRE_ENGINE" and config.AUTO_SUPPRESS and r.current_node != r.home_node \
            and eq.can_suppress() is None:
        _start_work(agent, "SUPPRESSING", task_id)
    else:
        _siren(agent, False)


def _start_work(agent: GroundResourceAgent, activity: str, task_id: str | None, until_s: float | None = None):
    rid = agent.resource.resource_id
    agent.resource.state = "WORKING"
    agent.resource.equipment.begin(activity, task_id, clock.now(), until_s)
    _works[rid] = asyncio.create_task(_work(agent, activity, task_id, until_s))


async def _work(agent: GroundResourceAgent, activity: str, task_id: str | None, until_s: float | None) -> None:
    """작업이 끝날 때까지 돈다. 진압은 물이 바닥나거나(EMPTY) 중지(STOPPED)될 때까지, 내리기는 UNLOAD_S."""
    r = agent.resource
    eq, rid = r.equipment, r.resource_id
    t = _tasks.get(task_id) if task_id else None
    start_s, start_water = clock.now(), eq.water_l
    rec = {"activity": activity, "status": "ACTIVE", "started_sim_s": round(start_s, 1)}
    if activity == "SUPPRESSING":
        rec.update(water_start_l=round(start_water, 1), pump_lps=eq.pump_lps)
        _siren(agent, True)
        gz_fx.spray(rid, True)
    if t is not None:
        t["work"] = rec
        _save()
    _report("UGV_WORK_STARTED", agent, task_id, **rec)
    result, last = "DONE", start_s
    try:
        while True:
            await asyncio.sleep(0.5)
            now = clock.now()
            if activity == "SUPPRESSING":
                eq.water_l = max(0.0, eq.water_l - (now - last) * eq.pump_lps)
                last = now
                rec["water_l"] = round(eq.water_l, 1)
                if eq.water_l <= 0:
                    result = "EMPTY"
                    break
            elif now >= until_s:
                break
    except asyncio.CancelledError:
        result = "STOPPED"
    now = clock.now()
    extra = {}
    if activity == "SUPPRESSING":
        gz_fx.spray(rid, False)
        extra = {"water_used_l": round(start_water - eq.water_l, 1), "water_l": round(eq.water_l, 1)}
    elif activity == "UNLOADING" and result == "DONE":
        extra = {"cargo": eq.cargo}
        if t is not None and t.get("cargo"):
            t["cargo"]["unloaded_sim_s"] = round(now, 1)
        eq.cargo = None
        gz_fx.cargo(rid, False)
    eq.end(now, result, **extra)
    rec.update(status=result, ended_sim_s=round(now, 1), duration_s=round(now - start_s, 1), **extra)
    _siren(agent, False)
    if r.state == "WORKING":
        r.state = "READY"
    if t is not None:
        _save()
    _works.pop(rid, None)
    _report("UGV_WORK_ENDED", agent, task_id, **rec)
    _resource_changed(agent, f"WORK_{result}")


async def _cancel_work(agent: GroundResourceAgent) -> bool:
    task = _works.get(agent.resource.resource_id)
    if task is None:
        return False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return True


@app.post("/ugv/{resource_id}/execute", response_model=ExecuteResponse)
async def execute(resource_id: str, req: ExecuteRequest):
    """Safety ALLOW 이후 호출. 주행을 시작하고 즉시 반환한다. 진행은 tracking_url 로 조회.

    UAV 와 같이 target(화재 좌표)을 받는다. 목적지 노드는 evaluate 와 같은 규칙(_decide)으로
    다시 고른다 — evaluate 이후 도로가 막혔으면 여기서 409 로 거절된다.
    cargo(+via_node) 가 있으면 싣기 → 주행 → 도착 → 내리기를 자동으로 한다 (_stages).
    """
    agent = _agent(resource_id)
    # 실행 키 확인이 먼저다: 같은 키 재요청은 수행 중이어도 기존 실행을 돌려준다 (UGV-04)
    # cargo·via_node 가 없으면 예전 요청과 같은 해시가 되도록 빼고 센다 (업그레이드 전 기록과 충돌하지 않게)
    body = {"resource_id": resource_id,
            **req.model_dump(exclude={k for k in ("cargo", "via_node") if getattr(req, k) is None})}
    verdict, meta = STORE.check(req.task_id, body)
    if verdict == "CONFLICT":
        raise HTTPException(409, {"reason": "EXECUTION_ID_CONFLICT", "task_id": req.task_id,
                                  "detail": "같은 실행 키로 다른 내용의 실행이 이미 있다 (기존 실행 유지)"})
    if verdict == "DUPLICATE":
        return ExecuteResponse(**{**meta["response"], "duplicate": True,
                                  "current_status": _tasks.get(req.task_id, {}).get("status")})
    if _task_of.get(resource_id):
        raise HTTPException(409, f"{resource_id} 는 task {_task_of[resource_id]} 수행 중")

    d = _decide(agent, req.target, req.target_node, req.cargo, req.via_node, req.target_mode)
    sp = d["stop_point"]
    spd = {} if sp is None else {"stop_point": sp.model_dump()}
    if d["verdict"] != "ACCEPT":
        raise HTTPException(409, f"실행 불가: {d['reason']} — {d['detail']}")   # 실행 안 함 → 키를 쓰지 않는다
    node_id = d["target_node"].node_id
    url = f"/ugv/{resource_id}/task/{req.task_id}"
    cargo = None if req.cargo is None else {"name": req.cargo.name, "kg": req.cargo.kg, "via_node": req.via_node}
    stages = _stages(node_id, req.via_node, req.cargo)
    if d["at_target"] and cargo is None:          # 이미 목적지(노드·도로 위 지점)에 서 있다 — 움직이지 않고 바로 완료
        r = agent.resource
        resp = ExecuteResponse(task_id=req.task_id, resource_id=resource_id, status="STARTED", tracking_url=url,
                               target_node=d["target_node"], eta_sec=0, stop_point=sp)
        STORE.register(req.task_id, body, {
            "task_id": req.task_id, "resource_id": resource_id, "status": "COMPLETED", "target_node": node_id, **spd,
            "progress": {"phase": "ARRIVED", "waypoint": 0, "total": 0},
            "observation": {"observation_type": "ROAD_STATUS", "arrived_node": node_id,
                            "position": {"lat": r.lat, "lon": r.lon}, "fuel_pct": r.fuel_pct}},
            resp.model_dump())
        _report("UGV_ARRIVED", agent, req.task_id, target_node=node_id, already_there=True,
                observation=_tasks[req.task_id]["observation"], **spd)
        _after_arrival(agent, req.task_id)
        return resp
    clock.release()                               # 환경 시계를 기다리며 멈춰 있었다면 첫 출발부터 흐른다
    if stages[0][0] == "DRIVE" and not await agent.execute(stages[0][1], _rp(sp)):
        raise HTTPException(500, "드라이버가 주행을 시작하지 못했다")

    resp = ExecuteResponse(task_id=req.task_id, resource_id=resource_id, status="STARTED", tracking_url=url,
                           target_node=d["target_node"], eta_sec=d["eta_sec"], stop_point=sp)
    STORE.register(req.task_id, body, {"task_id": req.task_id, "resource_id": resource_id, "status": "STARTED",
                                       "target_node": node_id, "progress": None, "observation": None, **spd,
                                       "cargo": cargo, "started_sim_s": round(clock.now(), 1),
                                       "eta_sec": d["eta_sec"]},
                   resp.model_dump())
    _task_of[resource_id] = req.task_id
    if stages[0][0] == "DRIVE":
        _siren(agent, True)
    _watchers[req.task_id] = asyncio.create_task(_run_task(req.task_id, agent, stages, d["eta_sec"]))
    _report("UGV_TASK_STARTED", agent, req.task_id, decision_id=req.decision_id, target_node=node_id,
            eta_sec=d["eta_sec"], path=d["path"], cargo=cargo, **spd)
    return resp


@app.post("/ugv/{resource_id}/stop")
async def stop(resource_id: str):
    """주행 중지. 진행 중 task 는 CANCELLED. 멈춘 곳에서 가장 가까운 도로 노드에 선 것으로 본다."""
    agent = _agent(resource_id)
    task_id = _task_of.get(resource_id)
    was = agent.resource.state
    watcher = _watchers.get(task_id) if task_id else None
    if watcher:
        watcher.cancel()
    stopped_work = await _cancel_work(agent)     # 진압·내리기 중이면 그것도 멈춘다 (기록 STOPPED)
    await agent.stop()
    _siren(agent, False)
    if task_id and task_id in _tasks:
        _tasks[task_id]["status"] = "CANCELLED"
        _tasks[task_id]["error"] = "stopped by request"
        _save()
        _report("UGV_TASK_CANCELLED", agent, task_id, reason="STOP_REQUESTED")
    _task_of[resource_id] = None
    if was != agent.resource.state or task_id:
        _resource_changed(agent, "RELEASED" if was == "UNAVAILABLE" else "STOPPED")
    r = agent.resource
    return {"resource_id": resource_id, "cancelled_task": task_id, "stopped_work": stopped_work, "state": r.state,
            "current_node": r.current_node, "position": {"lat": r.lat, "lon": r.lon}}


@app.post("/ugv/{resource_id}/suppress")
async def suppress(resource_id: str, req: SuppressRequest):
    """진압 제어 (소방차). [봉인: UGV_SUPPRESSION=1 일 때만 start 가능] 켜져 있으면 도착 즉시 시작하므로 보통은 stop 만 쓴다.
      stop  : 진압을 멈추고 READY (기록 status=STOPPED). 차는 그 자리에 선다
      start : 지금 자리에서 진압 시작 — READY 이고 수행 중 task 가 없고 물이 남아 있을 때만
    """
    agent = _agent(resource_id)
    eq = agent.resource.equipment
    if req.action == "stop":
        if eq is None or eq.activity != "SUPPRESSING":
            raise HTTPException(409, f"{resource_id} 는 진압 중이 아니다 (activity={None if eq is None else eq.activity})")
        await _cancel_work(agent)
        return {"resource_id": resource_id, "state": agent.resource.state, "equipment": eq.to_dict()}
    if not config.SUPPRESSION_ENABLED:
        raise HTTPException(409, "진압 불가: 진압 기능 봉인 (발표 범위 외, UGV_SUPPRESSION=1 이면 사용)")
    why = "장비 없음" if eq is None else eq.can_suppress()
    if why:
        raise HTTPException(409, f"진압 불가: {why}")
    if agent.resource.state != "READY" or _task_of.get(resource_id):
        raise HTTPException(409, f"진압 불가: {resource_id} 상태 {agent.resource.state}, task {_task_of.get(resource_id)}")
    _start_work(agent, "SUPPRESSING", req.task_id)
    return {"resource_id": resource_id, "state": agent.resource.state, "equipment": eq.to_dict()}


@app.get("/ugv/{resource_id}/task/{task_id}", response_model=TaskStatus)
async def get_task(resource_id: str, task_id: str):
    t = _tasks.get(task_id)
    if t is None or t["resource_id"] != resource_id:
        raise HTTPException(404, f"{resource_id} 의 task {task_id} 없음")
    return t


# --- 도로 환경 (차단·혼잡) ---------------------------------------------------
# 도로 환경은 UGV 것이고 환경 모듈(화재)과 별개다. 기본은 시나리오 파일(시간대별)이 정하고,
# 아래 API 는 시연·시험 중 직접 덧붙일 때 쓴다. 차단은 출처(scenario/manual/cells)별로 따로 기록된다.

@app.get("/roads")
async def road_status():
    """지금 막힌 도로(출처 포함)·경유 불가 노드·혼잡 도로."""
    return {"sim_time_s": round(clock.now(), 1), "blocked": roads.blocked(), "blocked_by": roads.blocked_by(),
            "blocked_nodes": roads.blocked_nodes(), "congested": roads.congested()}


@app.post("/roads/{road_id}/block")
async def block_road(road_id: str, req: BlockRequest):
    """도로 하나를 직접 막거나 푼다 (출처 manual). 시나리오 차단과 따로 기록되어 서로 풀지 않는다."""
    try:
        roads.set_blocked(road_id, req.blocked, "manual")
    except KeyError:
        raise HTTPException(404, f"도로 {road_id} 없음")
    r = fleet.graph.get_road(road_id)
    return {"road_id": road_id, "blocked": r.blocked, "blocked_by": roads.blocked_by().get(road_id, [])}


@app.post("/roads/nodes/{node_id}/block")
async def block_node(node_id: str, req: BlockRequest):
    """노드를 경유 불가로 (닿은 도로 전부 차단, 출처 manual). blocked=false 로 푼다."""
    try:
        affected = roads.set_node_blocked(node_id, req.blocked, "manual")
    except KeyError:
        raise HTTPException(404, f"도로 노드 {node_id} 없음")
    return {"node_id": node_id, "blocked": req.blocked, "roads": affected,
            "blocked_nodes": roads.blocked_nodes().get(node_id, [])}


@app.post("/roads/closures/cells")
async def close_cells(req: CellsRequest):
    """격자 칸 묶음을 지나는 도로를 한꺼번에 막는다 (구역 통제, 출처 cells).
    매 호출이 전체 목록(스냅샷)이다 — 이전 호출로 막은 도로는 풀고 다시 계산, 빈 목록이면 전부 해제.
    (예전 /env/fire_cells. 화재가 도로를 막지 않기로 해서 구역 통제로 이름만 바꿨다)"""
    return roads.apply_cells([(c.x, c.y) for c in req.cells], req.margin)


@app.post("/roads/congestion")
async def update_congestion(req: CongestionRequest):
    """혼잡 직접 설정. preset 은 전체를 먼저 1.0 으로 되돌린다.
    시나리오 혼잡 시간대가 켜져 있는 도로는 다음 갱신(1초) 때 시나리오 값으로 다시 덮인다."""
    try:
        out = roads.apply_congestion(req.preset, req.seed, req.ratio, req.min_factor,
                                     req.max_factor, req.roads)
    except (ValueError, KeyError) as e:
        raise HTTPException(422, str(e))
    if scenario is not None:
        scenario.resync()
    return out


@app.get("/roads/geometry")
async def road_geometry(only_changed: bool = False):
    """시각화용 도로 선형과 상태. only_changed=true 면 막혔거나 혼잡한 도로만."""
    out = []
    for rid, r in fleet.graph._roads.items():
        if only_changed and not r.blocked and r.congestion == 1.0:
            continue
        out.append({"road_id": rid, "name": r.name, "blocked": r.blocked, "congestion": r.congestion,
                    "blocked_by": roads.blocked_by().get(rid, []), "geometry": r.geometry})
    return {"sim_time_s": round(clock.now(), 1), "roads": out}


# --- 시계·시나리오 -------------------------------------------------------------

@app.get("/reports")
async def reports(limit: int = 30):
    """총괄에 보낸(보낼) 보고 최근 목록과 전송 통계. UGV_REPORT_URL 이 비면 기록만 하고 보내지 않는다."""
    return {**reporter.info(), "recent": reporter.recent[-limit:]}


@app.get("/clock")
async def get_clock():
    """시뮬레이션 시각. environment = 환경 시계 따라가기 상태, scenario_start_kst = 시뮬레이션 0초의 실제 시각."""
    return clock.info() | {"environment": dict(_env_clock), "scenario_start_kst": _start_kst()}


@app.post("/clock/env")
async def sync_env_clock(req: EnvClockRequest):
    """환경 스텝을 알려 준다. 시뮬레이션 초 = sim_step × UGV_SECONDS_PER_ENV_STEP 로 맞춘다.
    스텝이 줄었으면 새 실행으로 보고 시나리오를 처음부터 다시 적용한다."""
    res = clock.sync_env(req.sim_step)
    if res["reset"] and scenario is not None:
        scenario.reset(roads)
    if scenario is not None:
        scenario.tick(clock.now(), roads)
    return res | {"clock": clock.info()}


@app.get("/scenario")
async def get_scenario():
    if scenario is None:
        return {"name": None, "detail": "시나리오 없음 (UGV_SCENARIO 비어 있음)"}
    return scenario.info(clock.now())


@app.post("/scenario/reset")
async def reset_scenario(sim_time_s: float = 0.0):
    """시계를 sim_time_s 로 되돌리고 시나리오 차단·혼잡을 처음부터 다시 적용한다 (시연 반복용)."""
    clock.reset(sim_time_s)
    if scenario is not None:
        scenario.reset(roads)
        scenario.tick(clock.now(), roads)
    return {"clock": clock.info(), "scenario": None if scenario is None else scenario.info(clock.now())}


@app.get("/ugv/{resource_id}/route")
async def get_route(resource_id: str):
    """주행 중 경로 선형 [[lat, lon], ...] 과 남은 거리·시간. 시각화용."""
    agent = _agent(resource_id)
    agent.refresh()
    if agent.plan is None:
        return {"resource_id": resource_id, "route": [], "path": []}
    cur, total = agent.driver.progress()
    return {"resource_id": resource_id, "target_node": agent.plan.target_node, "path": agent.plan.path,
            "route": [list(p) for p in agent.route], "waypoint": cur, "total": total,
            "reroutes": agent.reroutes, "legs": _route_legs(agent), **_remaining(agent, cur)}


def _route_legs(agent: GroundResourceAgent) -> list[dict]:
    """경로를 도로 구간으로 — 상황판의 구간별 소요시간. 지금 도로 상태(차단·혼잡)로 다시 계산한다.
    state: DONE(지나옴) / CURRENT(달리는 중) / NEXT(남음). travel_s = 그 차 최고속도·지금 혼잡 기준 통과 시간."""
    path = agent.plan.path if agent.plan else []
    cur_road = agent.current_road_id()
    out, seen_current = [], cur_road is None
    for a, b in zip(path, path[1:]):
        try:
            r = fleet.graph.road_between(a, b)
        except KeyError:
            continue
        t = r.travel_s(agent.max_speed_mps)
        if not seen_current and r.road_id == cur_road:
            state, seen_current = "CURRENT", True
        else:
            state = "NEXT" if seen_current else "DONE"
        out.append({"road_id": r.road_id, "name": r.name, "from": a, "to": b, "distance_m": round(r.distance_m),
                    "congestion": r.congestion, "blocked": r.blocked,
                    "travel_s": None if t == float("inf") else round(t), "state": state})
    tail = next((l for l in (agent.plan.legs if agent.plan else []) if l.get("to_point")), None)
    if tail is not None:                       # 도로 위 지점 주행: 끝 노드 → 지점 꼬리 구간
        r = fleet.graph.get_road(tail["road_id"])
        on_tail = agent.driver is not None and agent.plan.current_leg(agent.driver.progress()[0]) is tail
        if on_tail:
            for o in out:
                o["state"] = "DONE"
        state = "CURRENT" if on_tail else "NEXT"
        sp = r.speed_mps(agent.max_speed_mps)
        out.append({"road_id": r.road_id, "name": r.name, "from": tail["from"], "to": None, "to_point": tail["to_point"],
                    "distance_m": round(tail["distance_m"]), "congestion": r.congestion, "blocked": r.blocked,
                    "travel_s": None if r.blocked else round(tail["distance_m"] / sp), "state": state})
    return out


def _bases() -> list[dict]:
    out = {}
    for a in fleet.agents.values():
        nid = a.resource.home_node
        if nid not in out:
            n = fleet.graph.node(nid)
            out[nid] = {"node_id": nid, "lat": n.lat, "lon": n.lon, "name": n.name or nid}
    return list(out.values())


@app.get("/graph/nodes")
async def graph_nodes():
    """도로 노드 전체 (상황판 표시용). degree = 닿은 도로 수 (2 가 아니면 교차로·끝점)."""
    g = fleet.graph
    return [{"node_id": nid, "lat": n.lat, "lon": n.lon, "name": n.name or "", "degree": len(g._adj.get(nid, []))}
            for nid, n in g._nodes.items()]


class ViewDispatch(BaseModel):
    node_id: str | None = None
    point: LatLon | None = None       # 노드 대신 도로 위 지점. 총괄은 칸(90 m) 중심으로 보낸다 —
                                      # 도로 위 점에 서려면 UGV_TARGET_MODE=road_point (아니면 가장 가까운 노드)
    resource_type: str = "UGV"        # UGV / FIRE_ENGINE — 어느 차가 갈지는 총괄이 고른다


@app.post("/view/dispatch")
async def view_dispatch(req: ViewDispatch):
    """상황판에서 노드를 눌러 출동 요청 → 총괄 POST /tasks 로 전달한다 (UGV 를 직접 움직이지 않는다).
    임무 = 그 지점까지 이동 (sensor 없음 → 총괄은 도착으로 완료, 환경 반영 ACK 없음). 차 선택·Safety 는 총괄 몫.
    다른 센서로 보내지 않는 이유 (2026-10-08 확인):
      WEATHER     — 총괄은 목표 칸이 화재·위험 칸 목록에 있을 때만 측정을 '목표 달성'으로 쳐서,
                    임의 도로 노드로는 도착·측정·재출동이 끝없이 되풀이된다.
      ROAD_STATUS — 총괄 능력표에 소방차는 ROAD_STATUS 가 없어 후보에서 빠진다 (UGV 만 감).
    브라우저가 총괄(:8200)을 직접 부르면 다른 출처(CORS)라 막히므로 이 서버가 대신 보낸다."""
    import uuid
    import httpx
    if req.resource_type not in ("UGV", "FIRE_ENGINE"):
        raise HTTPException(422, "resource_type 은 UGV 또는 FIRE_ENGINE")
    if req.point is not None:
        n = None
        tgt, label = {"lat": req.point.lat, "lon": req.point.lon}, "point"
    else:
        if req.node_id is None:
            raise HTTPException(422, "node_id 또는 point 중 하나가 필요하다")
        try:
            n = fleet.graph.node(req.node_id)
        except KeyError:
            raise HTTPException(404, f"도로 노드 {req.node_id} 없음")
        tgt, label = {"lat": n.lat, "lon": n.lon}, req.node_id
    rid = f"UGV-VIEW:{label}:{req.resource_type}:{uuid.uuid4().hex[:8]}"
    body = {"request_id": rid, "incident_id": "INC-UGV-VIEW", "kind": "RECON",
            "target": tgt,
            "requirements": {"resource_types": [req.resource_type], "sensor": None}}
    url = f"{config.ORCH_URL.rstrip('/')}/tasks"
    try:
        async with httpx.AsyncClient(timeout=15) as cx:
            r = await cx.post(url, json=body)
        out = r.json()
    except Exception as e:      # noqa: BLE001 — 총괄이 없으면 이유만 돌려준다
        out, r = {"error": f"{type(e).__name__}: {e}"}, None
    status = None if r is None else r.status_code
    task = (out or {}).get("task") or {}
    disp = (out or {}).get("dispatch") or {}
    if history is not None:
        history.record("VIEW_DISPATCH", None, task.get("task_id"), node_id=req.node_id,
                       nodes=[{"node_id": n.node_id, "lat": n.lat, "lon": n.lon} if n is not None
                              else {**tgt, "label": "도로 위 지점"}],
                       resource_type=req.resource_type, request_id=rid, orch_http=status,
                       purpose_status=task.get("purpose_status"), hold_reason=task.get("hold_reason"),
                       dispatch=disp.get("status") if isinstance(disp, dict) else disp,
                       attempt_id=disp.get("attempt_id") if isinstance(disp, dict) else None,
                       assigned=disp.get("resource_id") if isinstance(disp, dict) else None,
                       error=(out or {}).get("error") or (None if status in (200, 202) else (out or {}).get("detail")))
    return {"orch_http": status, "request": body, "response": out}


@app.get("/graph/edges")
async def graph_edges():
    """도로(간선) 전체 — 양 끝 노드·이름·길이. 상황판 그래프 보기가 교차로 사이를 한 간선으로 묶는 데 쓴다."""
    return [{"road_id": rid, "a": r.node_a, "b": r.node_b, "name": r.name or "", "distance_m": round(r.distance_m)}
            for rid, r in fleet.graph._roads.items()]


# --- 상황판: 차량 상태 요약 · 직접 명령 · 지형 ---------------------------------

_orch_cache: dict = {"t": 0.0, "tasks": {}, "attempt_task": {}}


async def _orch_purposes(attempt_ids) -> dict:
    """총괄 실행시도 ID → 임무 요약 (작전 이유 표시용). 시도→임무는 /attempts/{id} 로 한 번만 묻고 기억,
    임무 목록(/tasks)은 3초 캐시. 총괄이 없거나 느리면 빈 값 (상황판은 그대로 뜬다)."""
    import httpx
    ids = [a for a in attempt_ids if a and a.startswith("ATT-")]
    if not ids:
        return {}
    base = config.ORCH_URL.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=1.5) as cx:
            for a in ids:
                if a not in _orch_cache["attempt_task"]:
                    r = await cx.get(f"{base}/attempts/{a}")
                    if r.status_code == 200:
                        _orch_cache["attempt_task"][a] = r.json().get("task_id")
            now = time.monotonic()
            if now - _orch_cache["t"] > 3.0:
                rows = (await cx.get(f"{base}/tasks")).json()
                _orch_cache["tasks"] = {t.get("task_id"): t for t in (rows if isinstance(rows, list) else [])}
                _orch_cache["t"] = now
    except Exception:          # noqa: BLE001 — 총괄이 없어도 상황판은 뜬다
        pass
    out = {}
    for a in ids:
        tid = _orch_cache["attempt_task"].get(a)
        t = _orch_cache["tasks"].get(tid) if tid else None
        if tid:
            out[a] = {"orch_task_id": tid, "kind": (t or {}).get("kind"), "incident_id": (t or {}).get("incident_id"),
                      "request": (t or {}).get("request_key"), "purpose_status": (t or {}).get("purpose_status")}
    return out


def _purpose_text(task_id: str | None, info: dict | None) -> str | None:
    if not task_id:
        return None
    if task_id.startswith("VIEW-CMD-"):
        return "상황판 직접 명령 (운영자)"
    if not info:
        return "총괄 임무" if task_id.startswith("ATT-") else None
    req = info.get("request") or ""
    src = ("상황판 출동 요청" if req.startswith("UGV-VIEW") else "자동 초기 정찰" if req.startswith("AUTO-RECON")
           else "야간 순찰" if "PATROL" in req else "관제판 출동" if req.startswith("WEB-") else "총괄 임무")
    return f"{src} · {info.get('kind') or ''} · 총괄 {info.get('orch_task_id')}"


@app.get("/view/vehicles")
async def view_vehicles():
    """상황판 차량 목록: 상태 + 지금 임무(목적지·단계·남은 시간·작전 이유) + 지금 자리(노드 또는 도로 A→B)."""
    purposes = await _orch_purposes([_task_of.get(rid) for rid in fleet.agents])
    out = []
    for rid, agent in fleet.agents.items():
        agent.refresh()
        r = agent.resource
        tid = _task_of.get(rid)
        t = _tasks.get(tid) if tid else None
        place = {"at_node": r.current_node}
        if agent.parked is not None and r.state == "READY":       # 도로 위 지점에 서 있다
            place = {"road_id": agent.parked.road_id, "road_name": _road_name(agent.parked.road_id), "point": True,
                     "near_node": r.current_node}
        task = None
        if t is not None:
            prog = t.get("progress") or {}
            if agent.plan is not None and r.state == "RUNNING":
                cur = next((l for l in _route_legs(agent) if l["state"] == "CURRENT"), None)
                if cur:
                    place = {"road_id": cur["road_id"], "road_name": cur["name"], "from": cur["from"], "to": cur["to"]}
            tgt = t.get("target_node") or (agent.plan.target_node if agent.plan else None)
            started = t.get("started_sim_s")
            spt = t.get("stop_point")
            task = {"task_id": tid, "status": t.get("status"), "phase": prog.get("phase"),
                    "target_node": tgt, "stop_point": spt,
                    "target_name": f"{_road_name(spt['road_id'])} 위 지점" if spt else _node_name(tgt),
                    "eta_remaining_s": prog.get("eta_remaining_sec"), "remaining_m": prog.get("remaining_m"),
                    "started_sim_s": started, "reroutes": len(t.get("reroutes") or []),
                    "purpose": _purpose_text(tid, purposes.get(tid))}
        out.append({"resource_id": rid, "resource_type": r.resource_type, "base": r.base, "state": r.state,
                    "position": {"lat": r.lat, "lon": r.lon}, "current_node": r.current_node,
                    "current_node_name": _node_name(r.current_node), "place": place, "task": task,
                    "fault": agent.fault, "sim_time_s": round(clock.now(), 1)})
    return out


def _road_name(rid: str) -> str:
    try:
        return fleet.graph.get_road(rid).name or rid
    except KeyError:
        return rid


def _node_name(nid: str | None) -> str | None:
    if not nid:
        return None
    try:
        return fleet.graph.node(nid).name or None
    except KeyError:
        return None


class ViewCommand(BaseModel):
    resource_id: str
    node_id: str | None = None
    point: LatLon | None = None   # 노드 대신 도로 위 지점 (가장 가까운 도로 선형 위 점에 선다, ugv/road_point.py)
    replace: bool = False      # 임무 중인 차를 세우고 새 목적지로 보낼지 (상황판이 먼저 묻는다)


@app.post("/view/command")
async def view_command(req: ViewCommand):
    """상황판에서 차를 골라 노드를 누른 경우 — 그 차에 직접 명령한다 (운영자 명령, 총괄 Safety 를 거치지 않음).
    임무 중이면 replace=true 일 때만: 세우고(stop) → 평가 → 출발. 평가는 차가 서 있어야 된다 (주행 중이면 BUSY).
    총괄이 맡긴 임무(ATT-*)를 교체하면 그 임무는 FAILED(OPERATOR_OVERRIDE) 로 닫는다 — 총괄은 실패로 보고
    다른 자원에 인계한다 (CANCELLED 로 두면 총괄 계약에 그 상태 처리가 없어 점유가 풀리지 않는다)."""
    import uuid
    agent = _agent(req.resource_id)
    node = None
    if req.point is None:
        if req.node_id is None:
            raise HTTPException(422, "node_id 또는 point 중 하나가 필요하다")
        try:
            node = fleet.graph.node(req.node_id)
        except KeyError:
            raise HTTPException(404, f"도로 노드 {req.node_id} 없음")
    old = _task_of.get(req.resource_id)
    busy = old is not None and (_tasks.get(old) or {}).get("status") in ("STARTED", "IN_PROGRESS")
    if busy and not req.replace:
        raise HTTPException(409, {"reason": "BUSY", "task_id": old, "hint": "replace=true 로 다시 보내면 세우고 바꾼다"})
    stopped = None
    if busy or agent.resource.state == "UNAVAILABLE":
        stopped = await stop(req.resource_id)
        if old and old.startswith("ATT-") and old in _tasks:
            _tasks[old].update(status="FAILED", error="OPERATOR_OVERRIDE: 상황판 직접 명령으로 교체",
                               progress={**(_tasks[old].get("progress") or {}), "phase": "FAILED"})
            _save()
            _report("UGV_TASK_FAILED", agent, old, reason="OPERATOR_OVERRIDE", error="상황판 직접 명령으로 교체")
    tid, did = f"VIEW-CMD-{uuid.uuid4().hex[:8]}", f"VIEW-{uuid.uuid4().hex[:8]}"
    where = ({"target_node": node.node_id} if node is not None
             else {"target": req.point, "target_mode": "road_point"})
    ev = await evaluate(req.resource_id, EvaluateRequest(task_id=tid, decision_id=did, **where))
    sp = None if ev.stop_point is None else ev.stop_point.model_dump()
    result = {"resource_id": req.resource_id, "node_id": None if node is None else node.node_id, "stop_point": sp,
              "replaced_task": old if busy else None,
              "stopped": stopped is not None, "task_id": tid, "verdict": ev.verdict, "reason": ev.reason,
              "detail": ev.detail, "eta_sec": ev.eta_sec}
    if ev.verdict == "ACCEPT":
        ex = await execute(req.resource_id, ExecuteRequest(task_id=tid, decision_id=did, **where))
        result["status"] = ex.status
    if history is not None:
        pt = ({"node_id": node.node_id, "lat": node.lat, "lon": node.lon} if node is not None
              else {"lat": (sp or req.point.model_dump())["lat"], "lon": (sp or req.point.model_dump())["lon"],
                    "label": "도로 위 지점"})
        history.record("VIEW_COMMAND", req.resource_id, tid, node_id=result["node_id"], stop_point=sp, nodes=[pt],
                       replaced_task=result["replaced_task"], verdict=ev.verdict, reason=ev.reason, eta_sec=ev.eta_sec)
    return result


_terrain_cache: dict | None = None


@app.get("/view/terrain")
async def view_terrain():
    """지도 보기 배경: 환경 격자(90 m)의 고도·연료를 위경도 정렬 격자로 다시 뽑아 준다 (LIVE 화면과 같은 자료,
    web/static/inje2019/scenario.json). 색칠·음영은 브라우저가 한다. 격자는 EPSG:5186 이라 위경도와 약간 돌아가
    있어 네 모서리 좌표로 역변환해 표본을 뽑는다 (모서리 오차 수 m)."""
    global _terrain_cache
    if _terrain_cache is None:
        import base64
        import json
        import numpy as np
        src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "web", "static", "inje2019", "scenario.json")
        try:
            d = json.load(open(src, encoding="utf-8"))
        except OSError:
            raise HTTPException(404, "지형 자료 없음 (web/static/inje2019/scenario.json)")
        C, R = d["grid"]["cols"], d["grid"]["rows"]
        elev = np.frombuffer(base64.b64decode(d["elev_dm_u16"]), dtype=np.uint16).reshape(R, C)
        fuel = np.frombuffer(base64.b64decode(d["fuel_u8"]), dtype=np.uint8).reshape(R, C)
        try:
            import gz_bridge as gb
            corners = [gb.grid_cell_to_latlon(c, r) for c, r in ((-0.5, -0.5), (C - 0.5, -0.5), (-0.5, R - 0.5))]
        except Exception:      # noqa: BLE001 — 좌표 변환 라이브러리가 없으면 미리 계산해 둔 값 (2026-10-08)
            corners = [(38.10975038713186, 128.11850550827705), (38.10631696531064, 128.43449186224782),
                       (37.91842988279845, 128.11560158129583)]
        (la0, lo0), (la1, lo1), (la2, lo2) = corners
        # (col,row) → (lat,lon) 아핀: P = P0 + u·(P1-P0) + v·(P2-P0), u = (col+0.5)/C, v = (row+0.5)/R
        A = np.array([[la1 - la0, la2 - la0], [lo1 - lo0, lo2 - lo0]])
        Ainv = np.linalg.inv(A)
        lats = [la0, la1, la2, la1 + la2 - la0]
        lons = [lo0, lo1, lo2, lo1 + lo2 - lo0]
        s_, n_, w_, e_ = min(lats), max(lats), min(lons), max(lons)
        H, W = R * 2, C * 2
        la = np.linspace(n_, s_, H)[:, None] * np.ones((1, W))
        lo = np.ones((H, 1)) * np.linspace(w_, e_, W)[None, :]
        uv = np.einsum("ij,jhw->ihw", Ainv, np.stack([la - la0, lo - lo0]))
        col = np.floor(uv[0] * C).astype(int)
        row = np.floor(uv[1] * R).astype(int)
        inside = (col >= 0) & (col < C) & (row >= 0) & (row < R)
        cc, rr = np.clip(col, 0, C - 1), np.clip(row, 0, R - 1)
        e_out = np.where(inside, elev[rr, cc], 0).astype(np.uint16)
        f_out = np.where(inside, fuel[rr, cc], 255).astype(np.uint8)     # 255 = 격자 밖 (투명)
        _terrain_cache = {"w": W, "h": H, "bounds": [[s_, w_], [n_, e_]], "cell_m": d["grid"]["cell_m"],
                          "elev_dm_u16": base64.b64encode(e_out.tobytes()).decode(),
                          "fuel_u8": base64.b64encode(f_out.tobytes()).decode()}
    return _terrain_cache


@app.get("/graph/bases")
async def graph_bases():
    """거점 노드 (상황판 표시용)."""
    return _bases()


# --- 도로 상황판·실행 기록 (ugv/static/road_view.html, ugv/history.py) ------------

@app.get("/view", include_in_schema=False)
async def road_view():
    """UGV 도로 상황판. 이 서버 API 만 폴링한다 (총괄·관제판과 무관)."""
    return FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "road_view.html"))


@app.get("/history/runs")
async def history_runs():
    """실행(서버 기동) 목록, 최신 먼저. current=true 가 지금 실행."""
    return {"current": history.run_id if history.enabled else None, "runs": history.runs()}


@app.get("/history/runs/{run_id}")
async def history_events(run_id: str, after: int = 0, limit: int = 20000):
    """한 실행의 기록. after=seq 이후만 (실시간 화면은 이어 받기)."""
    try:
        return history.read(run_id, after, min(max(limit, 1), 50000))
    except KeyError:
        raise HTTPException(404, f"실행 기록 {run_id} 없음")
