# -*- coding: utf-8 -*-
"""웹 관제판: 강원 지형 + 산불 CA + 드론 실시간 + 화재 출동."""
import os, uuid, time, json
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import config
config.FIRE_CONNECTION_MODE = "real"
config.UAV_CONNECTION_MODE = "real"          # ▶ 변경: auto_tick이 uav_connector로 실제 서버에 붙게 함
# UGV 목록·위치는 박유홍님 실제 도로망 기반 브리지(integrated)에서 가져온다 (이전: 커넥터 mock 좌표)
config.UGV_CONNECTION_MODE = "integrated"
config.UAV_ENDPOINTS = {
    os.environ.get("UAV_ID", "A-uav1"): os.environ.get("UAV_AGENT_URL", "http://localhost:8000")
}                                             # ▶ 변경
from connectors import fire_connector, uav_connector, orchestrator_connector  # ▶ 변경: uav_connector, orchestrator_connector 추가
from interfaces.schema import ResourcePool   # ▶ 변경
from logger import EventLogger               # ▶ 변경
from main import process_task                # ▶ 변경
import ids                                   # ▶ 변경
import gz_bridge as gb
import math
from ugv.road_graph import RoadGraph
# 경로 그리기도 실제 도로망(roads_clipped.gpkg, 노드 534)을 쓴다 (이전: 데모 6노드 그래프)
from ugv.graph_gpkg import NODES, ROADS
from connectors import ugv_connector
from ugv.geo import distance_m
_RG = RoadGraph(NODES, ROADS)
_NODE_LL = {n["node_id"]:(n["lat"],n["lon"]) for n in NODES}
def _nearest_node(lat, lon):
    """(노드 id, 거리 m). 미터 거리로 비교 — 위경도 제곱합은 경도 방향을 과대평가한다."""
    best=None; bd=float("inf")
    for nid,(la,lo) in _NODE_LL.items():
        d=distance_m((lat,lon),(la,lo))
        if d<bd: bd=d; best=nid
    return best, bd

UAV_AGENT = os.environ.get("UAV_AGENT_URL", "http://localhost:8000")
UAV_ID    = os.environ.get("UAV_ID", "A-uav1")
WIND_MS   = float(os.environ.get("WEB_WIND_MS", "3.0"))
PREVIEW   = os.path.join(os.path.dirname(__file__), "static", "kangwon_terrain_preview.png")   # 강원 DEM 음영기복 (CA 격자 범위와 동일)
COLS, ROWS = 308, 236

from fastapi.staticfiles import StaticFiles
app = FastAPI(title="ADAIR 강원 관제판")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__),"static")), name="static")
_tick = 0
# 환경 시계는 서버가 소유한다. /api/env 는 이 간격이 지났을 때만 CA 를 한 스텝 진행하고,
# 그 외에는 현재 상태만 읽는다 → 브라우저 탭 수·폴링 주기와 무관하게 확산 속도가 일정하다.
WEB_ENV_STEP_SEC = float(os.environ.get("WEB_ENV_STEP_SEC", "1.5"))
_last_advance = 0.0

class FlyReq(BaseModel):
    col: int; row: int

@app.get("/api/preview")
def preview():
    if os.path.exists(PREVIEW): return FileResponse(PREVIEW, media_type="image/png")
    raise HTTPException(404, "no preview")

_COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _env_server_snapshot():
    """INT-05: 환경 계약 서버(/snapshot)를 읽기만 한다. 진행(/advance)은 트윈 시계만 부른다."""
    s = httpx.get(f"{config.WEB_ENV_URL}/snapshot", timeout=3).json()

    def xy(c):
        x, y = str(c["cell_id"]).split("_")
        return {"x": int(x), "y": int(y)}

    risk = sorted(s.get("risk_cells") or [], key=lambda c: -float(c.get("risk_score") or 0))[:150]
    to_deg = (float(s.get("wind_dir_deg") or 0) + 180) % 360          # 바람이 불어 가는 쪽 = 번지는 쪽
    return {"tick": s.get("step_count"), "fire": [xy(c) for c in s.get("fire_cells") or []],
            "risk": [xy(c) for c in risk], "wind_speed": s.get("wind_ms"),
            "spread": _COMPASS[int((to_deg + 22.5) // 45) % 8],
            "simulation_time_s": s.get("simulation_time_s"), "state_version": s.get("state_version"),
            "source": "ENV_SERVER"}


def _current_sim_time() -> float:
    """기록에 남길 시뮬레이션 시각 (공통데이터규약 §1)."""
    if config.WEB_ENV_URL:
        try:
            return float(httpx.get(f"{config.WEB_ENV_URL}/snapshot", timeout=2).json()["simulation_time_s"])
        except Exception:
            return 0.0
    return float(_tick)


@app.get("/api/env")
def env():
    """환경 상태 반환(격자 x,y). 환경 서버 모드면 읽기만, 아니면 서버 시계(WEB_ENV_STEP_SEC)로 CA 진행."""
    if config.WEB_ENV_URL:
        try:
            return _env_server_snapshot()
        except Exception as e:
            return {"tick": None, "fire": [], "risk": [], "wind_speed": None, "spread": "-",
                    "source": "ENV_SERVER", "error": f"환경 서버 응답 없음: {e}"}
    global _tick, _last_advance
    now = time.monotonic()
    advance = (now - _last_advance) >= WEB_ENV_STEP_SEC
    if advance:
        _tick += 1
    es = fire_connector.get_environment_state(float(_tick), advance=advance)
    if advance:
        _last_advance = time.monotonic()   # 계산이 끝난 시점 기준 (첫 호출의 엔진 로딩 시간 제외)
    fire = [{"x": c["x"], "y": c["y"]} for c in es.fire_cells]
    risk = [{"x": c["x"], "y": c["y"]} for c in es.risk_zone[:150]]
    return {"tick": _tick, "fire": fire, "risk": risk,
            "wind_speed": es.wind_speed, "spread": es.spread_direction}

@app.get("/api/orch")
def orch_summary():
    """INT-03: 총괄 판단 요약 (읽기 전용).

    총괄 서버의 /health, /priority/board 를 받아 관제판 우측 패널에 필요한 것만 추린다.
    관제판은 총괄 상태를 바꾸지 않는다 (출동·해소 버튼 없음). 상세 판단은 총괄의 /board 에서 본다.
    """
    base = config.ORCH_URL.rstrip("/")
    out = {"connected": False, "url": base, "board_url": f"{base}/board"}
    try:
        health = httpx.get(f"{base}/health", timeout=1.5).json()
        board = httpx.get(f"{base}/priority/board", timeout=1.5).json()
    except Exception:
        return out
    # 목적 상태와 기체(실행 시도) 상태는 따로 보여 준다 — 완료됐어도 기체는 복귀 중일 수 있다 (요청서 INT-03)
    attempts = {}
    try:
        st = httpx.get(f"{base}/state", timeout=1.5).json()
        for a in st.get("active_attempts") or []:
            attempts[a.get("task_id")] = {"substatus": a.get("substatus"), "resource_id": a.get("resource_id")}
    except Exception:
        pass
    env = health.get("truth_env") or {}
    known = board.get("known") or {}
    tasks = []
    for t in (board.get("auto_order") or [])[:8]:
        tasks.append({k: t.get(k) for k in ("task_id", "kind", "cell_id", "purpose_status", "hold_reason",
                                            "resume_condition", "resource_id", "risk_score", "human_risk")})
        att = attempts.get(t.get("task_id")) or {}
        tasks[-1]["attempt"] = att.get("substatus")
        tasks[-1]["resource_id"] = tasks[-1]["resource_id"] or att.get("resource_id")
    out.update({
        "connected": True,
        "env_class": env.get("class"), "env_shared": bool(env.get("shared_team_env")),
        "run_id": known.get("run_id"), "sim_time_s": known.get("simulation_time_s"),
        "mode": board.get("mode"),
        "llm_ready": not (board.get("llm") or {}).get("not_ready_reason"),
        "fires": len(known.get("fires") or []),
        "groups": len(board.get("groups") or []),
        "tasks": tasks,
    })
    return out

@app.get("/api/modes")
def modes():
    """관제판 상단 표시용: 지금 이 관제판이 어떤 모드로 실행 중인지.

    - demo_extinguish: INT-02 시연 전용 진화 스위치 (서버 시작 시 WEB_DEMO_EXTINGUISH 로 결정)
    - uav_mode: 연결된 UAV 서버의 /health 응답 mode (mock / real), 연결 실패 시 None
    """
    uav_mode = None
    try:
        uav_mode = httpx.get(f"{UAV_AGENT}/health", timeout=1.5).json().get("mode")
    except Exception:
        pass
    return {"demo_extinguish": bool(config.WEB_DEMO_EXTINGUISH),
            "dispatch_via_orch": bool(config.WEB_DISPATCH_VIA_ORCH),
            "env_url": config.WEB_ENV_URL or None, "stations_source": config.STATIONS_SOURCE,
            "uav_agent": UAV_AGENT, "uav_id": UAV_ID, "uav_mode": uav_mode}

@app.get("/api/state")
async def state():
    async with httpx.AsyncClient(timeout=10) as cx:
        r = await cx.get(f"{UAV_AGENT}/uav/{UAV_ID}/state"); r.raise_for_status()
        return r.json()

@app.get("/api/cell")
def cell(lat: float, lon: float):
    try:
        x, y = gb.latlon_to_epsg(lat, lon)
        return {"col": int((x-gb.GRID_LEFT)/gb.GRID_RES), "row": int((gb.GRID_TOP-y)/gb.GRID_RES)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/ugv")
def ugv(col: int = 60, row: int = 70):
    # 자원 목록: UGV/소방차 위치·capability (integrated — 실제 거점 노드)
    try:
        res = ugv_connector.get_ugv_status("A")
    except Exception:
        res = []
    units=[]
    for r in res:
        units.append({"id": r.resource_id, "type": r.resource_type,
                      "lat": r.location_lat, "lon": r.location_lon,
                      "cap": r.capability or {}})
    # 화재셀 → 위경도 → 최근접 도로노드(goal)
    flat, flon = gb.grid_cell_to_latlon(col, row)
    goal, goal_dist = _nearest_node(flat, flon)
    snap_limit = getattr(config, "UGV_TARGET_SNAP_M", 2000.0)
    routes=[]
    for u in units:
        if goal_dist > snap_limit:
            # 화재 근처에 도로 노드가 없음 → 임의 노드로 경로를 그리지 않는다
            routes.append({"id": u["id"], "reachable": False, "eta_sec": None, "path": [],
                           "err": "GOAL_TOO_FAR"})
            continue
        start, _ = _nearest_node(u["lat"], u["lon"])
        try:
            rr = _RG.find_route(start, goal)
            path = [{"lat": _NODE_LL[nid][0], "lon": _NODE_LL[nid][1]} for nid in getattr(rr,"path",[]) or []]
            routes.append({"id": u["id"], "reachable": rr.reachable,
                           "eta_sec": getattr(rr,"eta_s",None), "path": path})
        except Exception as e:
            routes.append({"id": u["id"], "reachable": False, "eta_sec": None, "path": [], "err": str(e)})
    # 차단 도로 수
    blocked = sum(1 for rd in ROADS if rd.get("blocked"))
    return {"fire_cell":{"col":col,"row":row,"lat":round(flat,6),"lon":round(flon,6)},
            "goal_node": goal, "goal_distance_m": round(goal_dist, 1), "units": units, "routes": routes, "blocked_roads": blocked}

@app.post("/api/extinguish")
def extinguish(cell: dict):
    """자원이 도착한 화재셀을 진화 처리(관측으로 UNBURNED 반영).

    INT-02: 시연 전용. config.WEB_DEMO_EXTINGUISH 가 꺼져 있으면(기본) 환경을 바꾸지 않는다.
    """
    rid = cell.get("resource_id")
    if not config.WEB_DEMO_EXTINGUISH or config.WEB_ENV_URL:
        _web_log("ARRIVAL", "ARRIVED", resource_id=rid, reason="DEMO_EXTINGUISH_OFF",
                 detail={"source": "WEB_MANUAL", "cell": [cell.get("col"), cell.get("row")], "extinguish_applied": False})
        return {"ok": False, "disabled": True, "reason": "DEMO_EXTINGUISH_OFF"}
    try:
        col=int(cell["col"]); row=int(cell["row"])
        lat,lon=gb.grid_cell_to_latlon(col,row)
        x,y=gb.latlon_to_epsg(lat,lon)
        api=fire_connector._engine()   # 강원 CA 엔진
        r=api.apply_observation({"reporter_id":"RESPONSE","world_x":x,"world_y":y,"fire_state":"UNBURNED"})
        _web_log("ARRIVAL", "ARRIVED", resource_id=rid, reason="DEMO_EXTINGUISH",
                 detail={"source": "WEB_MANUAL", "cell": [col, row], "extinguish_applied": bool(r.get("success"))})
        return {"ok": bool(r.get("success")), "cell": [col,row]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ===== 자동 폐루프 =====
# ▶ 변경: 이제 판단·배정·Safety 검사는 orchestrator_connector + process_task 가 전담한다.
#         이 dict는 "화면에 어떤 셀을 목표로 보여줄지"만 기억하는 용도다.
_AUTO = {"on": False, "target": None, "t": 0}
_AUTO_LOGGER = EventLogger(run_id=ids.new_run_id(), scenario_id="WEB-AUTO", file_name="web_auto.jsonl")  # ▶ 변경


def _web_log(event_type, result, **kw):
    """관제판의 수동 출동·도착도 자동 루프와 같은 로그 파일(web_auto.jsonl)에 남긴다.
    출처는 detail.source 로 구분한다 (WEB_MANUAL / WEB_AUTO / WEB_VIA_ORCH). 기록 실패가 화면 동작을 막지 않게 한다."""
    try:
        _AUTO_LOGGER.log_event(event_type, _current_sim_time(), result=result, **kw)
    except Exception as e:
        print(f"[web log] 기록 실패: {e}")

@app.post("/api/auto/toggle")
def auto_toggle():
    if config.WEB_ENV_URL:   # INT-05: 시계 하나 — 관제판 자체 자동 루프는 환경을 따로 진행시키므로 끈다
        return {"on": False, "disabled": True,
                "reason": "환경 서버 모드: 자동 판단·배정은 총괄이 담당합니다 (관제판 자체 자동 루프 꺼짐)"}
    _AUTO["on"] = not _AUTO["on"]
    if _AUTO["on"]:
        _AUTO["target"] = None
    return {"on": _AUTO["on"]}

@app.post("/api/auto/tick")  # ▶ 변경: 함수 전체 재작성
# async 가 아닌 일반 함수로 둔다: 안의 process_task 가 UAV 서버를 동기 HTTP 로 부르므로(수 초),
# async 로 두면 그동안 서버 전체가 멈춰 "자동 중지"·지도 갱신 요청까지 대기하게 된다.
def auto_tick():
    if not _AUTO["on"]:
        return {"on": False, "events": []}
    ev = []
    try:
        # 환경은 진행시키지 않는다(시계는 /api/env 가 소유) — 기존 규칙 유지
        es = fire_connector.get_environment_state(float(_AUTO["t"]), advance=False)
        _AUTO["t"] += 1
        if not es.fire_cells:
            return {"on": True, "events": ["화재 없음 - 대기"], "target": _AUTO["target"]}

        if _AUTO["target"] is None:
            best = max(es.fire_cells, key=lambda c: c.get("risk_score", 0.0))
            _AUTO["target"] = {"col": best["x"], "row": best["y"]}
            ev.append("감지: 셀(%d,%d)" % (best["x"], best["y"]))

        # 화재 좌표 확정, 후보 선택, 재평가, Safety 검증은 기존 검증된 폐루프가 전담한다.
        task = orchestrator_connector.create_task(float(_AUTO["t"]), es)
        if not getattr(task, "target_resolved", True):
            ev.append("타깃 확정 실패: " + str(getattr(task, "unresolved_reason", "")))
            _AUTO["target"] = None
            return {"on": True, "events": ev, "target": None}

        pool = ResourcePool(base_a=uav_connector.get_uav_status("A"), base_b=[])
        task, es = process_task(task, es, pool, _AUTO_LOGGER, float(_AUTO["t"]))
        ev.append(f"Task {task.task_id}: {task.state}")

        if task.state in ("COMPLETED", "FAILED", "CANCELLED"):
            _AUTO["target"] = None  # 다음 tick에서 새 화재를 다시 고름
    except Exception as e:
        ev.append("출동 오류: " + str(e))
    return {"on": True, "events": ev, "target": _AUTO["target"]}

@app.post("/api/auto/done")
def auto_done():
    t = _AUTO.get("target")
    applied = False
    if t and config.WEB_DEMO_EXTINGUISH:   # INT-02: 시연 전용 스위치가 켜졌을 때만 진화 반영
        try:
            lat,lon = gb.grid_cell_to_latlon(t["col"], t["row"]); x,y = gb.latlon_to_epsg(lat,lon)
            fire_connector._engine().apply_observation({"reporter_id":"AUTO","world_x":x,"world_y":y,"fire_state":"UNBURNED"})
            applied = True
        except Exception:
            pass
    if t:
        _web_log("ARRIVAL", "ARRIVED", reason="DEMO_EXTINGUISH" if config.WEB_DEMO_EXTINGUISH else "DEMO_EXTINGUISH_OFF",
                 detail={"source": "WEB_AUTO", "cell": [t.get("col"), t.get("row")], "extinguish_applied": applied})
    _AUTO["target"] = None
    return {"ok": True}

@app.post("/api/fly")
async def fly(req: FlyReq):
    try:
        lat, lon = gb.grid_cell_to_latlon(req.col, req.row)
        target = {"lat": round(lat,6), "lon": round(lon,6), "alt_m_amsl": round(gb.terrain_elev(req.col,req.row),1)}
    except Exception as e:
        # 고도를 확정하지 못하면 출동하지 않는다 (fail-closed)
        return {"ok": False, "verdict": None, "reason": "TARGET_UNRESOLVED", "detail": str(e)}
    if config.WEB_DISPATCH_VIA_ORCH:
        return await _fly_via_orch(req, target)
    tid = "WEB-"+uuid.uuid4().hex[:8]; did = "DEC-"+uuid.uuid4().hex[:8]
    base = {"task_id": tid, "decision_id": did, "target": target, "observation_type": "THERMAL"}
    async with httpx.AsyncClient(timeout=30) as cx:
        # 풍속은 환경모델 값을 싣는다 (김동현님 R01_R05 6-2). 조회 실패 시에만 WEB_WIND_MS 사용
        try:
            if config.WEB_ENV_URL:
                wind = httpx.get(f"{config.WEB_ENV_URL}/snapshot", timeout=3).json()["wind_ms"]
            else:
                wind = fire_connector.get_environment_state(float(_AUTO["t"]), advance=False).wind_speed
        except Exception:
            wind = WIND_MS
        _web_log("TASK_CREATED", "READY", task_id=tid,
                 detail={"source": "WEB_MANUAL", "cell": [req.col, req.row], "target": target})
        ev = (await cx.post(f"{UAV_AGENT}/uav/{UAV_ID}/evaluate", json={**base,"wind_ms":wind})).json()
        _web_log("LOCAL_RESPONSE", ev.get("verdict") or "UNKNOWN", reason=ev.get("reason"), decision_id=did,
                 task_id=tid, resource_id=UAV_ID,
                 detail={"source": "WEB_MANUAL", "evidence": {"eta_sec": ev.get("eta_sec"),
                         "constraints": ev.get("constraints"), "counter_offer": ev.get("counter_offer")}})
        if ev.get("verdict") != "ACCEPT":
            _web_log("TASK_COMPLETE", "FAILED", reason=ev.get("reason") or ev.get("verdict"), decision_id=did,
                     task_id=tid, resource_id=UAV_ID, detail={"source": "WEB_MANUAL"})
            return {"ok": False, "verdict": ev.get("verdict"), "reason": ev.get("reason"), "target": target}
        ex = (await cx.post(f"{UAV_AGENT}/uav/{UAV_ID}/execute", json=base)).json()
        # 수동(직접) 경로는 총괄 Safety 를 거치지 않는다 — INT-01 스위치를 켜면 총괄 경유로 바뀐다
        _web_log("EXECUTION", "STARTED", reason="MANUAL_DIRECT_NO_SAFETY", decision_id=did,
                 task_id=tid, resource_id=UAV_ID, detail={"source": "WEB_MANUAL"})
    return {"ok": True, "task_id": ex.get("task_id", tid), "target": target, "eta_sec": ev.get("eta_sec")}

async def _fly_via_orch(req: FlyReq, target: dict) -> dict:
    """INT-01: 관제판 출동을 총괄 POST /tasks 로 보낸다 (UAV 직접 호출 없음).

    클릭 한 번 = request_id 하나. 같은 request_id 재전송은 총괄이 같은 임무로 처리한다.
    접수(202)는 출동 성공이 아니다 — 진행은 총괄 판단 패널(/priority/board)에서 본다.
    """
    body = {"request_id": "WEB-FLY-" + uuid.uuid4().hex[:12], "kind": "RECON",
            "target": {"lat": target["lat"], "lon": target["lon"],
                       "ground_amsl_m": target["alt_m_amsl"], "cell_id": f"{req.col}_{req.row}"},
            "requirements": {"resource_types": ["UAV"], "sensor": "THERMAL"}}
    try:
        async with httpx.AsyncClient(timeout=30) as cx:
            r = await cx.post(f"{config.ORCH_URL.rstrip('/')}/tasks", json=body)
        j = r.json()
    except Exception as e:
        _web_log("ORCH_TASK_SUBMITTED", "FAILED", reason="ORCH_UNREACHABLE",
                 detail={"source": "WEB_VIA_ORCH", "request_id": body["request_id"], "cell": [req.col, req.row]})
        return {"ok": False, "via": "orch", "reason": "ORCH_UNREACHABLE", "detail": str(e), "target": target}
    if r.status_code not in (200, 202):
        _web_log("ORCH_TASK_SUBMITTED", "FAILED", reason=f"ORCH_HTTP_{r.status_code}",
                 detail={"source": "WEB_VIA_ORCH", "request_id": body["request_id"], "cell": [req.col, req.row]})
        return {"ok": False, "via": "orch", "reason": f"ORCH_HTTP_{r.status_code}", "detail": j, "target": target}
    t = j.get("task") or {}
    # 접수(202)는 출동 성공이 아니다. 이후 진행은 총괄 장부가 기록하므로 여기서는 접수 사실만 남긴다
    _web_log("ORCH_TASK_SUBMITTED", "ACCEPTED", task_id=t.get("task_id"), reason=t.get("hold_reason"),
             detail={"source": "WEB_VIA_ORCH", "request_id": body["request_id"], "cell": [req.col, req.row],
                     "purpose_status": t.get("purpose_status"), "created": j.get("created")})
    return {"ok": True, "via": "orch", "request_id": body["request_id"], "task_id": t.get("task_id"),
            "created": j.get("created"), "purpose_status": t.get("purpose_status"),
            "hold_reason": t.get("hold_reason"), "target": target}
# ── 디지털 트윈 LIVE (2019 인제) ─────────────────────────────────────────────
# 실제로 돌고 있는 서버들을 한 화면용으로 모은다. 계산은 하지 않는다 (각 서버가 진실의 출처).
#   환경 계약 서버(진짜 세계 CA, :8300) · UAV Agent(mock 또는 PX4 real, :8000/:8001) · UGV 서버(:8100) · 총괄(:8200)
TWIN_ENV_URL = os.environ.get("TWIN_ENV_URL", "http://127.0.0.1:8300")
TWIN_ORCH_URL = os.environ.get("TWIN_ORCH_URL", "http://127.0.0.1:8200")
TWIN_UGV_URL = os.environ.get("TWIN_UGV_URL", config.UGV_SERVER_URL)
TWIN_UAVS = dict(p.split("=", 1) for p in os.environ.get("TWIN_UAVS", "").split(",") if "=" in p) or {
    k: v for k, v in {"A-uav1": "http://127.0.0.1:8000", "A-uav2": "http://127.0.0.1:8001"}.items()}


def _ll_to_grid(lat, lon):
    x, y = gb.latlon_to_epsg(lat, lon)
    return round((x - gb.GRID_LEFT) / gb.GRID_RES - 0.5, 3), round((gb.GRID_TOP - y) / gb.GRID_RES - 0.5, 3)


@app.get("/api/twin")
async def twin_state():
    out = {"sources": {}, "fetched_wall": time.time()}
    async with httpx.AsyncClient(timeout=5.0) as cx:
        async def get(name, url):
            try:
                r = await cx.get(url)
                r.raise_for_status()
                out["sources"][name] = "OK"
                return r.json()
            except Exception as e:  # noqa: BLE001 — 한 서버가 없어도 나머지는 보여 준다
                out["sources"][name] = f"DOWN: {type(e).__name__}"
                return None
        snap = await get("env", f"{TWIN_ENV_URL}/snapshot")
        if snap:
            out["env"] = {k: snap.get(k) for k in ("run_id", "state_version", "simulation_time_s", "scenario_start_kst",
                                                    "wind_ms", "wind_dir_deg", "weather", "tick_s", "step_count")}
            out["fire"] = [[*map(int, c["cell_id"].split("_")), 1 if c["fire_state"] == "BURNING" else 2]
                           for c in snap.get("fire_cells", [])]
        out["uav"] = []
        for rid, url in TWIN_UAVS.items():
            st = await get(f"uav:{rid}", f"{url}/uav/{rid}/state")
            hl = await get(f"uav:{rid}:health", f"{url}/health") if st else None
            if st:
                p = st.get("position") or {}
                gx, gy = _ll_to_grid(p["lat"], p["lon"]) if p.get("lat") is not None else (None, None)
                out["uav"].append({"id": rid, "gx": gx, "gy": gy, "alt_m_amsl": p.get("alt_m_amsl"),
                                   "battery": (st.get("battery") or {}).get("percent"), "mode": (hl or {}).get("mode"),
                                   "flight_mode": st.get("flight_mode"), "task": st.get("current_task_id")})
        ck = await get("ugv:clock", f"{TWIN_UGV_URL}/clock")     # 연속 시계 (환경은 한 스텝씩 건너뛴다)
        out["clock_s"] = (ck or {}).get("sim_time_s")
        ug = await get("ugv", f"{TWIN_UGV_URL}/ugv")
        out["ugv"] = []
        for u in ug or []:
            p = u.get("position") or {}
            if p.get("lat") is None:
                continue
            gx, gy = _ll_to_grid(p["lat"], p["lon"])
            out["ugv"].append({"id": u["resource_id"], "type": u.get("resource_type"), "gx": gx, "gy": gy,
                               "state": u.get("state"), "task": u.get("current_task_id"), "driver": u.get("driver"),
                               "activity": u.get("activity"), "water_l": (u.get("equipment") or {}).get("water_l"),
                               "pump_on": (u.get("equipment") or {}).get("pump_on")})
            if u.get("current_task_id") and u.get("state") == "RUNNING":     # 주행 중이면 남은 거리·시간 (시뮬레이션 초)
                tk = await get(f"ugv:{u['resource_id']}:task",
                               f"{TWIN_UGV_URL}/ugv/{u['resource_id']}/task/{u['current_task_id']}")
                pg = (tk or {}).get("progress") or {}
                out["ugv"][-1].update(eta_s=pg.get("eta_remaining_sec"), remaining_m=pg.get("remaining_m"),
                                      leg=pg.get("stage"), rtb=str(u["current_task_id"]).startswith("RTB-"),
                                      # 물이 없어 거점을 거쳐 가는 출동의 첫 구간 (거점 → 보충 → 목적지)
                                      via_refill=pg.get("stage") == "1/3" and not (tk or {}).get("cargo"))
        tasks = await get("orchestrator", f"{TWIN_ORCH_URL}/tasks")
        if tasks is not None:
            rows = tasks if isinstance(tasks, list) else tasks.get("tasks", [])
            out["tasks"] = [{"id": t.get("task_id"), "kind": t.get("kind"), "status": t.get("purpose_status"),
                             "cell": (t.get("target") or {}).get("cell_id"), "hold": t.get("hold_reason")}
                            for t in rows][-12:]
    return out


# ---------------------------------------------------------------------------
# 시연 시나리오 (feat/demo-ground) — tools/demo_twin.sh 가 시나리오마다 트윈을 처음(14:45)부터 다시 띄운다
#   (선택 전)  아무 출동 없이 불만 번진다 (ORCH_AUTO_RECON=0)
#   공통      불 확인 → 총괄이 ① 화점 초기 진압 ② 보호선 2곳(남전1리 마을회관·인제휴게소) 출동을 받아 차량을 고른다.
#             가장 가까운 소방차(F-fire1, Gazebo 가능)가 화점에 가서 방수 — 물 3000 L 가 떨어지면 멈추고 거점으로 보충.
#             방수는 표시(퍼포먼스)일 뿐 불을 끄지 않는다 (환경 진화 효과 ENV-07 미완).
#   hq      인제119 본부 소방차(A-fire1)가 보호선으로. 드론은 B(현장 근처 이착륙)처럼 정찰. UGV 는 멀어서 안 쓴다
#   patrol  A-fire1 이 인근 순찰 중(설악로)이라 보호선에 빨리 도착. 드론은 B′(원통 기지) — 배터리 여유가 없어
#           정찰을 못 받으면 총괄이 UGV(열화상)로 대신 보낸다. UGV 여러 대가 드론 없이 순찰을 메우는지 보는 실험
#   시나리오별 환경(드론 이륙 위치·차량 시작 위치·UGV 대수)은 demo_twin.sh 가 정한다.
# ---------------------------------------------------------------------------
FIRE_ROAD_NODE = {"lat": 38.028288, "lon": 128.130269, "node_id": "494955"}   # 남전약수터 화점 앞 설악로
PROTECT_SITES = ("NAMJEON1_HALL", "INJE_REST_AREA")                           # scenario.json sites (사람 있는 시설)
DEMO_SCENARIOS = [
    {"id": "idle", "title": "⓪ 출동 없음 (불만 번짐)",
     "desc": "신고·정찰·출동 없이 불만 번진다. 처음 띄웠을 때 기본 상태. 비교 기준(아무것도 안 했다면).",
     "patrol": False, "idle": True},
    {"id": "hq", "title": "① 본부 출동 (드론 전진 배치)",
     "desc": "불 확인 → 가장 가까운 소방차가 화점 초기 진압(방수), 인제119 본부 소방차가 보호선으로. 드론은 현장 근처에서 이착륙(B).",
     "patrol": False},
    {"id": "patrol", "title": "② 인근 순찰차 출동 (드론 원통 기지 · UGV 대체)",
     "desc": "소방차가 인근 순찰 중이라 보호선에 빨리 도착. 드론은 원통 기지(B′)라 정찰을 못 받으면 총괄이 UGV 열화상으로 대신 보낸다.",
     "patrol": True},
]
_DEMO_RUNS = []          # 최근 실행 (화면 기록용)
_DEMO_BOOT = uuid.uuid4().hex[:8]          # 이 웹 서버 기동 id — 화면이 '다시 시작됐는지' 알아보는 데 쓴다
_DEMO_AUTO = {"sid": os.getenv("DEMO_AUTOSTART") or None, "status": None}
# 지금 돌고 있는 시나리오 (demo_twin.sh 가 DEMO_CURRENT 로 알려 준다. 처음 띄우면 idle)
_DEMO_CURRENT = os.getenv("DEMO_CURRENT") or (os.getenv("DEMO_AUTOSTART") or "idle")


async def _prologue(cx) -> dict:
    """공통 단계: 총괄이 '불 확인(CONFIRMED)' 한 칸과 확인한 자원"""
    import asyncio
    for i in range(3):                       # 총괄 board 일시 오류(500)는 잠깐 뒤 다시
        try:
            rb = await cx.get(f"{TWIN_ORCH_URL}/priority/board")
            rb.raise_for_status()
            b = rb.json()
            break
        except Exception as e:  # noqa: BLE001
            if i == 2:
                return {"ok": False, "why": f"총괄 연결 실패: {type(e).__name__}"}
            await asyncio.sleep(0.5)
    fires = [f for f in (b.get("known") or {}).get("fires", []) if f.get("status") == "CONFIRMED"]
    if not fires:
        if os.getenv("DEMO_SUPERVISED") == "1" and not _DEMO_AUTO["sid"]:
            return {"ok": False, "why": "출동 없이 불만 번지는 중 — 시나리오를 고르면 14:45 신고부터 다시 시작합니다"}
        return {"ok": False, "why": "아직 불 확인 전 — 신고 지점으로 정찰 중입니다 (시작 후 1~2분)"}
    f = fires[0]
    return {"ok": True, "cell_id": f["cell_id"], "resource_id": f.get("resource_id"),
            "sim_time_s": f.get("sim_time_s"), "source": f.get("source")}


@app.get("/api/demo/scenarios")
async def demo_scenarios():
    async with httpx.AsyncClient(timeout=5.0) as cx:
        pro = await _prologue(cx)
    return {"prologue": pro, "scenarios": [{k: v for k, v in sc.items() if k != "tasks"} for sc in DEMO_SCENARIOS],
            "runs": _DEMO_RUNS[-5:], "boot": _DEMO_BOOT, "supervised": os.getenv("DEMO_SUPERVISED") == "1",
            "autostart": _DEMO_AUTO,
            "current": next(({"id": x["id"], "title": x["title"]} for x in DEMO_SCENARIOS if x["id"] == _DEMO_CURRENT),
                            {"id": _DEMO_CURRENT, "title": _DEMO_CURRENT})}


@app.post("/api/demo/start/{sid}")
async def demo_start(sid: str):
    """시나리오를 처음부터: tools/demo_twin.sh 아래에서 돌면 트윈 전체를 다시 띄우고 불 확인 뒤 자동 실행한다.
    감시 스크립트 없이(run_twin.sh 직접) 돌면 지금 상태에 그대로 실행한다."""
    if not any(x["id"] == sid for x in DEMO_SCENARIOS):
        raise HTTPException(404, "없는 시나리오")
    flag = os.getenv("DEMO_RESTART_FLAG")
    if os.getenv("DEMO_SUPERVISED") == "1" and flag:
        with open(flag, "w", encoding="utf-8") as f:
            f.write(sid)
        return {"restarting": True, "boot": _DEMO_BOOT}
    if sid == "idle":
        return {"restarting": False, "run": None}
    return {"restarting": False, "run": await demo_run(sid)}


@app.on_event("startup")
async def _demo_autostart():
    """DEMO_AUTOSTART 시나리오: 불이 확인되면(공통 단계 끝) 바로 실행"""
    sid = _DEMO_AUTO["sid"]
    if not sid:
        return
    import asyncio

    async def go():
        _DEMO_AUTO["status"] = "WAITING_FIRE_CONFIRMED"
        flag = os.getenv("DEMO_RESTART_FLAG")
        for n in range(300):
            await asyncio.sleep(2)
            async with httpx.AsyncClient(timeout=5.0) as cx:
                pro = await _prologue(cx)
                # 첫 정찰이 접수만 되고 배정 작업자가 깨지 않는 경우가 있다 → 10초마다 배정을 한 번 부탁한다
                # (이미 배정됐으면 아무 일도 안 한다)
                if not pro.get("ok") and n % 5 == 4:
                    try:
                        await cx.post(f"{TWIN_ORCH_URL}/dispatch_pending", timeout=3.0)
                    except Exception:  # noqa: BLE001
                        pass
            # 시연: 총괄이 시작 직후 가끔 첫 정찰을 내보내지 못하고 멈춘다(원인 조사 중) → 90초 안에 불 확인이
            # 안 되면 트윈 전체를 같은 시나리오로 다시 띄운다 (정상이면 10배속에서 20초 안에 확인된다)
            if not pro.get("ok") and n == 45 and os.getenv("DEMO_AUTO_RESTART") == "1" and os.getenv("DEMO_SUPERVISED") == "1" and flag:
                _DEMO_AUTO["status"] = "RESTARTING_STUCK"
                with open(flag, "w", encoding="utf-8") as f:
                    f.write(sid)
                return
            if pro.get("ok"):
                try:
                    await demo_run(sid)
                    _DEMO_AUTO["status"] = "STARTED"
                except HTTPException as e:
                    _DEMO_AUTO["status"] = f"FAILED: {e.detail}"
                    if e.status_code == 409:     # 임무를 올리기 전(불 확인 단계) 실패 → 다시 시도
                        continue
                return
        _DEMO_AUTO["status"] = "TIMEOUT"
    asyncio.get_event_loop().create_task(go())


_MAP_CELLS: list = []


async def _site_cells(cx) -> dict:
    """보호 시설 → 가장 가까운 트윈 칸 (twin_ground_dispatch.py 와 같은 규칙: 공개 좌표 → 최근접 칸)"""
    global _MAP_CELLS
    if not _MAP_CELLS:
        _MAP_CELLS = (await cx.get(f"{TWIN_ENV_URL}/map_cells")).json()["cells"]
    scn = json.load(open(os.path.join(os.path.dirname(__file__), "static", "inje2019", "scenario.json"), encoding="utf-8"))
    out = {}
    for s_ in scn.get("sites", []):
        if s_["site_id"] in PROTECT_SITES:
            k = math.cos(math.radians(s_["lat"]))
            c = min(_MAP_CELLS, key=lambda c: (c["lat"] - s_["lat"]) ** 2 + ((c["lon"] - s_["lon"]) * k) ** 2)
            out[s_["site_id"]] = {"name": s_["name"], "cell": c}
    return out


async def _post_task(cx, body: dict) -> dict:
    r = await cx.post(f"{TWIN_ORCH_URL}/tasks", json=body)
    if r.status_code >= 300:
        raise HTTPException(r.status_code, {"step": "POST /tasks", "detail": r.json()})
    return r.json()


@app.post("/api/demo/run/{sid}")
async def demo_run(sid: str):
    sc = next((x for x in DEMO_SCENARIOS if x["id"] == sid), None)
    if sc is None or sc.get("idle"):
        raise HTTPException(404, "없는 시나리오")
    stamp = f"{time.strftime('%H%M%S')}-{uuid.uuid4().hex[:4]}"
    posted, results = [], {}
    async with httpx.AsyncClient(timeout=60.0) as cx:
        pro = await _prologue(cx)
        if not pro["ok"]:
            raise HTTPException(409, pro["why"])
        risk = (await cx.get(f"{TWIN_ORCH_URL}/view/risk_cells")).json().get("risk_cells", [])
        risk = [c for c in risk if isinstance(c.get("risk_score"), (int, float)) and c.get("lat") is not None]
        sites = await _site_cells(cx)

        # ① 화점 초기 진압 — 바로 배정 (가장 가까운 소방차가 받는다)
        r = await _post_task(cx, {
            "request_id": f"DEMO-{sid}-SCENE-{stamp}", "incident_id": "INC-DEMO", "kind": "GROUND_SUPPORT",
            "target": {"lat": FIRE_ROAD_NODE["lat"], "lon": FIRE_ROAD_NODE["lon"], "cell_id": pro["cell_id"]},
            "requirements": {"resource_types": ["FIRE_ENGINE"], "sensor": None},
            "area_cell_ids": [pro["cell_id"]], "dispatch": True})
        posted.append({"task_id": r["task"]["task_id"], "cell_id": pro["cell_id"], "risk_score": None,
                       "resource_type": "FIRE_ENGINE", "label": "화점 초기 진압"})
        results[r["task"]["task_id"]] = r.get("dispatch") or {}

        # ② 보호선 2곳 — 같이 접수하고 한 번에 배정 (둘 다 사람 있는 시설 → 비슷하면 총괄이 AI 에 순서를 묻는다)
        #    우선순위 근거: 시설 칸 + 그 시설에 가장 가까운 위험 칸 (불이 시설 쪽으로 오는 위험)
        for sid_ in PROTECT_SITES:
            if sid_ not in sites:
                continue
            c = sites[sid_]["cell"]
            near = min(risk, key=lambda x: distance_m((x["lat"], x["lon"]), (c["lat"], c["lon"]))) if risk else None
            cells = [c["cell_id"]] + ([near["cell_id"]] if near else [])
            r = await _post_task(cx, {
                "request_id": f"DEMO-{sid}-{sid_}-{stamp}", "incident_id": "INC-DEMO", "kind": "GROUND_SUPPORT",
                "target": {k: c.get(k) for k in ("lat", "lon", "ground_amsl_m", "cell_id")},
                "requirements": {"resource_types": ["FIRE_ENGINE"], "sensor": None},
                "area_cell_ids": cells, "dispatch": False})
            posted.append({"task_id": r["task"]["task_id"], "cell_id": c["cell_id"],
                           "risk_score": near["risk_score"] if near else None,
                           "resource_type": "FIRE_ENGINE", "label": f"보호선 · {sites[sid_]['name']}"})

        # ③ (hq) 드론 전진 배치(B): 화선 주변 열화상 순찰 2곳을 드론에 — 현장 근처에서 이착륙하니 바로 받는다
        if not sc["patrol"]:
            for i, c in enumerate(sorted(risk, key=lambda x: -x["risk_score"])[:2]):
                r = await _post_task(cx, {
                    "request_id": f"DEMO-{sid}-UAVPATROL{i}-{stamp}", "incident_id": "INC-DEMO", "kind": "RECON",
                    "target": {k: c.get(k) for k in ("lat", "lon", "ground_amsl_m", "cell_id")},
                    "requirements": {"resource_types": ["UAV"], "sensor": "THERMAL"},
                    "area_cell_ids": [c["cell_id"]], "dispatch": False})
                posted.append({"task_id": r["task"]["task_id"], "cell_id": c["cell_id"], "risk_score": c["risk_score"],
                               "resource_type": "UAV", "label": f"드론 열화상 순찰 {i + 1}"})

        # ③ (patrol) 화선 열화상 순찰. 먼저 드론(원통 기지)에 요청 → 배터리 여유가 없으면 드론이 스스로 거절(LOW_BATTERY)
        #    나머지 순찰 2곳은 드론·UGV 모두 허용 → 총괄이 더 가까운 UGV 를 보낸다 (드론 없이 UGV 여러 대가 메우는지)
        if sc["patrol"]:
            road = [(n["lat"], n["lon"]) for n in NODES]
            near_road = sorted(risk, key=lambda x: min(distance_m((x["lat"], x["lon"]), q) for q in road))[:3]
            if near_road:
                c = near_road[-1]
                r = await _post_task(cx, {
                    "request_id": f"DEMO-{sid}-UAVPATROL-{stamp}", "incident_id": "INC-DEMO", "kind": "RECON",
                    "target": {k: c.get(k) for k in ("lat", "lon", "ground_amsl_m", "cell_id")},
                    "requirements": {"resource_types": ["UAV"], "sensor": "THERMAL"},
                    "area_cell_ids": [c["cell_id"]], "dispatch": False})
                posted.append({"task_id": r["task"]["task_id"], "cell_id": c["cell_id"], "risk_score": c["risk_score"],
                               "resource_type": "UAV", "label": "드론 열화상 순찰 (원통 기지)"})
            for i, c in enumerate(near_road[:2]):
                r = await _post_task(cx, {
                    "request_id": f"DEMO-{sid}-PATROL{i}-{stamp}", "incident_id": "INC-DEMO", "kind": "RECON",
                    "target": {k: c.get(k) for k in ("lat", "lon", "ground_amsl_m", "cell_id")},
                    "requirements": {"resource_types": ["UAV", "UGV"], "sensor": "THERMAL"},
                    "area_cell_ids": [c["cell_id"]], "dispatch": False})
                posted.append({"task_id": r["task"]["task_id"], "cell_id": c["cell_id"], "risk_score": c["risk_score"],
                               "resource_type": "UAV/UGV", "label": f"열화상 순찰 {i + 1}"})

        t0 = time.monotonic()
        d = (await cx.post(f"{TWIN_ORCH_URL}/dispatch_pending")).json()
        took = round(time.monotonic() - t0, 2)
    for tid, res in (d.get("results") or {}).items():
        results.setdefault(tid, res)
    run = {"scenario": sid, "title": sc["title"], "wall": time.time(), "prologue": pro,
           "similar_pair": bool(d.get("groups")), "tasks": posted, "dispatch_s": took,
           "groups": [{"task_ids": g["task_ids"], "kinds": g.get("kinds"), "status": g.get("status"),
                       "llm": g.get("llm")} for g in d.get("groups", [])],
           "results": {p["task_id"]: {k: (results.get(p["task_id"]) or {}).get(k) for k in ("status", "resource_id", "reason")}
                       for p in posted}}
    _DEMO_RUNS.append(run)
    _start_patrol(sid, sc)
    return run


# --- 상황실 순찰 요청 반복 (재현 B 의 '매 스텝 화선 재관측'을 LIVE 에서) ------------------------
# 드론 2대가 쉬지 않고 돈다: 스텝마다 위험 칸 2곳(묶음 → AI 순서), 그 사이엔 화선 둘레를 한 칸씩. 총괄은 평소 절차
# (우선순위 → 묶음이면 AI 순서 → 차량 평가 → Safety) 그대로 배정한다. 직전 순찰이 아직 안 끝났으면 쌓지 않는다.
PATROL_PER_STEP = int(os.getenv("DEMO_PATROL_PER_STEP", "2"))      # 동시에 도는 순찰 수 (드론 대수)
PATROL_RECENT = int(os.getenv("DEMO_PATROL_RECENT", "6"))          # 최근 본 칸 몇 개를 건너뛸지
PATROL_RING_M = float(os.getenv("DEMO_PATROL_RING_M", "600"))     # 스텝 사이 둘레 순찰 반경
_PATROL = {"task": None, "rounds": 0}
_DONE = ("COMPLETED", "FAILED", "CANCELLED", "ABANDONED", "UNKNOWN")


def _start_patrol(sid: str, sc: dict) -> None:
    import asyncio
    if PATROL_PER_STEP <= 0 or _PATROL["task"] is not None:
        return
    _PATROL["task"] = asyncio.get_event_loop().create_task(_patrol_loop(sid, sc))


async def _patrol_loop(sid: str, sc: dict) -> None:
    """드론이 쉬지 않게 순찰을 이어 붙인다.
    - 환경이 한 스텝 나갈 때: 순찰 PATROL_PER_STEP 건을 한꺼번에 요청 (묶음 → 총괄이 AI 에 순서를 묻는다)
    - 그 사이: 끝난 순찰이 있으면 바로 다음 칸 1건을 요청 (단독이라 AI 없이 규칙으로 바로 배정)
    다음 칸 = 위험도 높은 순, 최근에 본 칸은 잠시 건너뛴다 (화선 둘레를 돌아가며 본다)."""
    import asyncio
    run0 = _DEMO_RUNS[-1] if _DEMO_RUNS else {}
    seen = [t["cell_id"] for t in run0.get("tasks", []) if "UAV" in (t.get("resource_type") or "")]
    last_step, mine, n = None, [], 0
    types = ["UAV", "UGV"] if sc["patrol"] else ["UAV"]

    ring_i = [0]

    def pick(risk, k):
        recent = set(seen[-PATROL_RECENT:])
        cand = [c for c in risk if c["cell_id"] not in recent] or risk
        return cand[:k]

    def ring(risk):
        """화선 둘레 순찰점: 위험 칸 상위 10개의 중심에서 PATROL_RING_M 떨어진 8방향을 차례로 돈다"""
        if not risk or not _MAP_CELLS:
            return None
        top = risk[:10]
        clat = sum(c["lat"] for c in top) / len(top); clon = sum(c["lon"] for c in top) / len(top)
        ang = math.radians(45 * (ring_i[0] % 8)); ring_i[0] += 3          # 3칸씩 건너뛰어 맞은편으로 오간다
        lat = clat + PATROL_RING_M * math.cos(ang) / 111_320
        lon = clon + PATROL_RING_M * math.sin(ang) / (111_320 * math.cos(math.radians(clat)))
        k = math.cos(math.radians(lat))
        return min(_MAP_CELLS, key=lambda m: (m["lat"] - lat) ** 2 + ((m["lon"] - lon) * k) ** 2)

    while True:
        await asyncio.sleep(3)
        try:
            async with httpx.AsyncClient(timeout=10.0) as cx:
                step = (await cx.get(f"{TWIN_ENV_URL}/snapshot")).json().get("step_count")
                new_step = last_step is not None and step != last_step
                last_step = step
                open_ = []
                for tid in mine:
                    st = (await cx.get(f"{TWIN_ORCH_URL}/tasks/{tid}")).json().get("purpose_status")
                    if st not in _DONE:
                        open_.append(tid)
                mine = open_
                free = PATROL_PER_STEP - len(mine)
                if free <= 0:
                    continue
                risk = (await cx.get(f"{TWIN_ORCH_URL}/view/risk_cells")).json().get("risk_cells", [])
                risk = [c for c in risk if isinstance(c.get("risk_score"), (int, float)) and c.get("lat") is not None]
                risk.sort(key=lambda x: -x["risk_score"])
                if new_step:                     # 새 스텝: 위험 칸 묶음 (AI 가 순서를 정한다)
                    cells = pick(risk, free)
                else:                            # 그 사이: 화선 둘레를 한 칸씩 (단독 → 규칙으로 바로 배정, AI 없음)
                    rc = ring(risk)
                    cells = [{**rc, "risk_score": None}] if rc else []
                if not cells:
                    continue
                n += 1
                _PATROL["rounds"] = n
                run = _DEMO_RUNS[-1] if _DEMO_RUNS else None
                for i, c in enumerate(cells):
                    r = await _post_task(cx, {
                        "request_id": f"DEMO-{sid}-PAT{n}-{i}-{time.strftime('%H%M%S')}", "incident_id": "INC-DEMO",
                        "kind": "RECON", "target": {kk: c.get(kk) for kk in ("lat", "lon", "ground_amsl_m", "cell_id")},
                        "requirements": {"resource_types": types, "sensor": "THERMAL"},
                        "area_cell_ids": [c["cell_id"]], "dispatch": not new_step})
                    tid = r["task"]["task_id"]
                    mine.append(tid)
                    seen.append(c["cell_id"])
                    _PATROL["last"] = {"n": n, "cell_id": c["cell_id"], "step": step}
                    if run is not None and new_step:     # 화면 기록은 스텝마다의 묶음만 (둘레 순찰은 횟수만 센다)
                        run["tasks"].append({"task_id": tid, "cell_id": c["cell_id"], "risk_score": c["risk_score"],
                                             "resource_type": "/".join(types),
                                             "label": f"순찰 {n} (스텝 {step}{' · 새 스텝' if new_step else ''})"})
                if new_step:
                    await cx.post(f"{TWIN_ORCH_URL}/dispatch_pending")
        except Exception as e:  # noqa: BLE001 — 순찰 반복은 멈추지 않는다
            print(f"[patrol] {type(e).__name__}: {e}", flush=True)


_TRAIL_TYPES = ("CANDIDATES_FILTERED", "LOCAL_RESPONSE", "SAFETY_JUDGEMENT", "EXECUTION", "OBSERVATION",
                "TASK_COMPLETED", "PURPOSE_STATUS", "HOLD")


def _trail_note(e: dict) -> str:
    """판단 단계 한 줄 요약 (화면용)"""
    d, t = e.get("detail") or {}, e.get("event_type")
    if t == "CANDIDATES_FILTERED":
        ok = ", ".join(c.get("resource_id", "?") if isinstance(c, dict) else
                       (f"{c[0]} 직선 {round(c[1] / 1000, 1)} km" if isinstance(c, (list, tuple)) and len(c) > 1
                        and isinstance(c[1], (int, float)) else str(c)) for c in d.get("candidates", []))
        ex = ", ".join(f"{k}:{v}" for k, v in (d.get("excluded") or {}).items())
        return f"후보 [{ok or '없음'}]  제외 [{ex or '없음'}]"
    if t == "LOCAL_RESPONSE":
        node = ((d.get("constraints") or {}).get("target_node") or {})
        eta = d.get("eta_sec_duration")
        return (f"ETA {round(eta / 60)}분 " if isinstance(eta, (int, float)) else "") + \
               (f"도로 노드 {node.get('node_id')} (스냅 {node.get('snap_m')} m)" if node else "")
    if t == "SAFETY_JUDGEMENT":
        return f"검사 {len(d.get('checked') or [])}항목"
    return ""


_LAST_BOARD = None          # 직전에 받은 총괄 board (일시 오류 때 재사용)


@app.get("/api/demo/ai")
async def demo_ai():
    """AI 판단 기록: 총괄의 LLM 상태·최근 호출(입력·출력)·묶음 결정 + 최근 시연 임무의 판단 단계"""
    out = {"llm": None, "groups": [], "trail": {}, "run": _DEMO_RUNS[-1] if _DEMO_RUNS else None,
           "patrol": {"rounds": _PATROL["rounds"], "last": _PATROL.get("last")}}
    async with httpx.AsyncClient(timeout=5.0) as cx:
        global _LAST_BOARD
        try:
            rb = await cx.get(f"{TWIN_ORCH_URL}/priority/board")
            rb.raise_for_status()
            b = _LAST_BOARD = rb.json()
        except Exception as e:  # noqa: BLE001
            # 총괄 /priority/board 가 가끔 500 (기상 지식 조회 경합) → 화면이 깜빡이지 않게 직전 값을 쓴다
            if _LAST_BOARD is None:
                out["error"] = f"총괄 연결 실패: {type(e).__name__}"
                return out
            b, out["board_cached"] = _LAST_BOARD, True
        out["llm"] = b.get("llm")
        out["mode"] = b.get("mode")
        out["groups"] = [{"task_ids": g["task_ids"], "kinds": g.get("kinds"), "status": g.get("status"),
                          "llm": g.get("llm"),
                          "tasks": [{k: t.get(k) for k in ("task_id", "cell_id", "risk_score", "distance_m",
                                                         "purpose_status", "resource_id")} for t in g.get("tasks", [])]}
                         for g in b.get("groups", [])]
        run_tasks = (out["run"] or {}).get("tasks", [])
        out["run_group"] = None
        for p_ in run_tasks:   # 배경 배정기가 먼저 묶음을 처리했어도 그 결정을 찾아 보여 준다 (묶음에 든 임무 아무거나)
            try:
                g = (await cx.get(f"{TWIN_ORCH_URL}/priority/group_of/{p_['task_id']}")).json().get("group")
            except Exception:  # noqa: BLE001
                g = None
            if g:
                out["run_group"] = g
                break
        for p in run_tasks:
            try:
                evs = (await cx.get(f"{TWIN_ORCH_URL}/tasks/{p['task_id']}/events")).json()
            except Exception:  # noqa: BLE001
                continue
            rows = evs if isinstance(evs, list) else evs.get("events", [])
            out["trail"][p["task_id"]] = [{"type": e.get("event_type"), "result": e.get("result"),
                                           "reason": e.get("reason"), "resource": e.get("resource_id"),
                                           "note": _trail_note(e)}
                                          for e in rows if e.get("event_type") != "PURPOSE_TRANSITION"][-12:]
    return out


@app.get("/inje3d")
def inje3d():
    """2019 인제 산불 '드론이 있었다면' 3D 재현 (three.js). 데이터: python tools/inje2019_whatif.py"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/static/inje2019/index.html")

@app.get("/", response_class=HTMLResponse)
def index(): return HTML

HTML = """<!DOCTYPE html><html lang=ko><head><meta charset=utf-8><title>ADAIR 강원 관제판</title>
<style>
body{margin:0;font-family:system-ui,'Malgun Gothic';background:#0f1720;color:#e6f2ef}
header{padding:12px 18px;background:#14273f;font-weight:800}
.wrap{display:flex;gap:14px;padding:14px;flex-wrap:wrap}
.map{position:relative;flex:1 1 560px;min-width:360px}
.map img{width:100%;display:block;border-radius:10px;border:1px solid #2a3a4d}
#ov{position:absolute;left:0;top:0;width:100%;height:100%}
.panel{flex:1 1 280px;min-width:260px;background:#16202b;border:1px solid #2a3a4d;border-radius:10px;padding:14px}
h3{margin:.2em 0 .5em;color:#8fd7c9}.row{display:flex;gap:8px;margin:8px 0;align-items:center}
input{width:74px;padding:7px;border-radius:8px;border:1px solid #3a4a5d;background:#0f1720;color:#e6f2ef}
button{padding:9px 14px;border:0;border-radius:8px;font-weight:700;cursor:pointer;color:#fff}
#fly{background:#e0483a}#clr{background:#3a5c99}
.kv{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #22303f}
.kv b{color:#8fd7c9}.log{font-family:monospace;font-size:12px;color:#9fe;white-space:pre-wrap;background:#0d1f14;border:1px solid #0C8E7E;border-radius:8px;padding:8px;margin-top:8px}
small{color:#6f8a96}
.modes{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 6px}
.badge{font-size:12px;font-weight:700;padding:3px 9px;border-radius:999px;border:1px solid #3a4a5d;color:#9fb3bf;background:#0f1720}
.badge.on{color:#1b1206;background:#f0a33a;border-color:#f0a33a}
.badge.real{color:#06131a;background:#5fd0ff;border-color:#5fd0ff}
.badge.bad{color:#fff;background:#8a2b2b;border-color:#8a2b2b}
.orch{font-size:12px;margin-top:4px}
.orch .meta{color:#9fb3bf;margin:4px 0 6px}
.orch table{width:100%;border-collapse:collapse}
.orch td{padding:3px 4px;border-top:1px solid #22303d;vertical-align:top}
.st{display:inline-block;padding:1px 7px;border-radius:999px;font-weight:700;font-size:11px;white-space:nowrap}
.st.wait{background:#2a3644;color:#c9d6de}.st.go{background:#1f5d8c;color:#fff}.st.ok{background:#1f7a4d;color:#fff}
.st.fail{background:#8a2b2b;color:#fff}.st.cancel{background:#3a3a3a;color:#bbb}
.orch .why{color:#8fa3ae;font-size:11px}
.orch a,h3 small a{color:#5fd0ff}
</style></head><body>
<header>🔥🚁 ADAIR — 강원 지형 · 산불 · 드론 실시간</header>
<div class=wrap>
 <div class=map>
   <img id=terrain src=/api/preview>
   <canvas id=ov></canvas>
   <small>빨강=연소중 · 주황=위험 · 청록=드론 · 파랑선=비행궤적 · 노랑=출동 타깃</small>
 </div>
 <div class=panel>
   <h3>출동</h3>
   <div class=modes><span id=mExt class=badge>진화 시연: 확인 중</span><span id=mUav class=badge>드론 서버: 확인 중</span><span id=mDisp class=badge>출동 경로: 확인 중</span><span id=mClock class=badge>산불 시계: 확인 중</span></div>
   <div class=row>col <input id=col type=number value=60> row <input id=row type=number value=70>
     <button id=fly>🔥 출동</button><button id=clr>궤적 지우기</button><button id=auto style="background:#0C8E7E">자동 시작</button></div>
   <h3>산불(CA)</h3>
   <div class=kv><b>연소 셀</b><span id=nfire>-</span></div>
   <div class=kv><b>바람</b><span id=wind>-</span></div>
   <h3>드론</h3>
   <div class=kv><b>lat</b><span id=lat>-</span></div>
   <div class=kv><b>lon</b><span id=lon>-</span></div>
   <div class=kv><b>고도</b><span id=alt>-</span></div>
   <div class=kv><b>모드</b><span id=mode>-</span></div>
   <div class=kv><b>타깃거리</b><span id=dist>-</span></div>
   <h3>지상자원(UGV)</h3><div class=kv><b>상태</b><span id=ugvinfo>-</span></div>
   <h3>자원 목록</h3><div id=fleet style="font-size:12px"></div>
   <div class=log id=log>대기…</div>
   <h3>총괄 판단 <small>(읽기 전용 · 상세는 <a id=orchLink href="#" target=_blank>/board</a>)</small></h3>
   <div class=modes><span id=mOrch class=badge>총괄 서버: 확인 중</span><span id=mEnv class=badge>환경: -</span></div>
   <div class=orch><div class=meta id=orchMeta>-</div><table id=orchTasks></table></div>
 </div>
</div>
<script>
const COLS=308,ROWS=236,$=id=>document.getElementById(id);
const img=$('terrain'),ov=$('ov');
let fire=[],risk=[],drone=null,tgt=null,trail=[];
function fit(){ov.width=img.clientWidth;ov.height=img.clientHeight;}
img.onload=fit;window.onresize=fit;
function P(c,r){return [(c+0.5)/COLS*ov.width,(r+0.5)/ROWS*ov.height];}
let _cellCache={};
function llCell(lat,lon){const k=lat.toFixed(5)+','+lon.toFixed(5);
  if(_cellCache[k])return _cellCache[k];
  // 서버 /api/cell 은 async라, 근사: DEM transform 역산을 클라에서(간이)
  const GRID_LEFT=298096,GRID_TOP=612773,RES=90; // EPSG:5186 근사 — 데모용
  // 위경도→EPSG 근사는 서버가 정확. 여기선 캐시 미스 시 중앙 반환 후 서버 보정
  return _cellCache[k]||{col:154,row:118};}
// 로버 주행 애니: 유닛별 경로 진행률(0~1) 상태
let _driveT={}, _extd={};          // {unitId: 진행률}
let _driveStart={};      // {unitId: 시작 시각}
function pathPointAt(rt,u){
  // rt.path(노드 col/row) 를 따라 u(0~1) 위치 보간
  const pts=(rt.path||[]).filter(p=>p.col!=null);
  if(pts.length<2) return pts[0]||null;
  const seg=(pts.length-1)*Math.max(0,Math.min(1,u));
  const i=Math.min(pts.length-2,Math.floor(seg)); const f=seg-i;
  return {col:pts[i].col+(pts[i+1].col-pts[i].col)*f,
          row:pts[i].row+(pts[i+1].row-pts[i].row)*f};
}
function hav(a,b,c,d){const R=6371000,r=Math.PI/180;
 const dp=(c-a)*r,dl=(d-b)*r,A=Math.sin(dp/2)**2+Math.cos(a*r)*Math.cos(c*r)*Math.sin(dl/2)**2;
 return 2*R*Math.asin(Math.sqrt(A));}
function draw(){const g=ov.getContext('2d');g.clearRect(0,0,ov.width,ov.height);
 risk.forEach(c=>{const[x,y]=P(c.x,c.y);g.fillStyle='rgba(224,140,40,.5)';g.fillRect(x-2,y-2,4,4);});
 fire.forEach(c=>{const[x,y]=P(c.x,c.y);g.fillStyle='rgba(224,60,40,.9)';g.beginPath();g.arc(x,y,3.5,0,7);g.fill();});
 if(tgt){const[x,y]=P(tgt.col,tgt.row);g.strokeStyle='#ffd23a';g.lineWidth=3;g.beginPath();g.arc(x,y,9,0,7);g.stroke();
   g.fillStyle='#ffd23a';g.beginPath();g.arc(x,y,3,0,7);g.fill();}
 if(trail.length>1){g.strokeStyle='#4aa3ff';g.lineWidth=2.5;g.beginPath();
   trail.forEach((p,i)=>{const[x,y]=P(p.col,p.row);i?g.lineTo(x,y):g.moveTo(x,y);});g.stroke();}
// UGV 자원·도로경로
 if(window.__ugv){const U=window.__ugv;
   (U.routes||[]).forEach(rt=>{ if(rt.path&&rt.path.length>1){
     g.strokeStyle=rt.reachable?'rgba(230,150,40,.9)':'rgba(150,150,150,.6)';g.lineWidth=3;g.beginPath();
     rt.path.forEach((p,i)=>{if(p.col==null)return;const[x,y]=P(p.col,p.row);i?g.lineTo(x,y):g.moveTo(x,y);});g.stroke();}});
   U._pos={};
   (U.units||[]).forEach(u=>{
     const rt=(U.routes||[]).find(r=>r.id===u.id);
     let pos=null;
     if(rt&&rt.reachable&&rt.path&&rt.path.length>1){pos=pathPointAt(rt,_driveT[u.id]||0);}
     if(!pos&&u.col!=null)pos={col:u.col,row:u.row};
     if(!pos)return; U._pos[u.id]=pos;
     const[x,y]=P(pos.col,pos.row);
     const fire=(u.type==='FIRE_ENGINE');
     const sz=fire?11:8;
     g.fillStyle=fire?'#ff3b30':'#e8912a';g.fillRect(x-sz,y-sz,sz*2,sz*2);
     g.strokeStyle='#fff';g.lineWidth=2;g.strokeRect(x-sz,y-sz,sz*2,sz*2);
     if(fire){g.fillStyle='#fff';g.font='bold 11px sans-serif';g.textAlign='center';g.fillText('🚒',x,y+4);}
     g.fillStyle='#cfe';g.font='11px sans-serif';g.textAlign='left';g.fillText(u.id,x+sz+3,y+4);
     if((_driveT[u.id]||0)>=0.999){g.strokeStyle='#ffd23a';g.lineWidth=2.5;g.beginPath();g.arc(x,y,sz+5,0,7);g.stroke();}
   });
 }
 if(drone){const[x,y]=P(drone.col,drone.row);
   if(tgt){const[tx,ty]=P(tgt.col,tgt.row);g.strokeStyle='rgba(74,163,255,.5)';g.setLineDash([6,6]);g.lineWidth=2;
     g.beginPath();g.moveTo(x,y);g.lineTo(tx,ty);g.stroke();g.setLineDash([]);}
   g.fillStyle='#00d1b2';g.beginPath();g.arc(x,y,7,0,7);g.fill();
   g.strokeStyle='rgba(0,209,178,.5)';g.lineWidth=4;g.beginPath();g.arc(x,y,12,0,7);g.stroke();}}
async function tickEnv(){try{const e=await(await fetch('/api/env')).json();fire=e.fire;risk=e.risk;
 $('nfire').textContent=fire.length;$('wind').textContent=(e.wind_speed==null?'-':e.wind_speed+' m/s '+e.spread)+(e.source==='ENV_SERVER'&&e.simulation_time_s!=null?' · 시뮬 '+Math.round(e.simulation_time_s/60)+'분':'');draw();}catch(e){}}
let lastLL=null;
async function tickState(){try{const s=await(await fetch('/api/state')).json();const p=s.position||{};
 $('lat').textContent=p.lat;$('lon').textContent=p.lon;$('alt').textContent=(p.alt_m_amsl)+' m';
 $('mode').textContent=s.flight_mode;
 if(p.lat!=null){const g=await(await fetch('/api/cell?lat='+p.lat+'&lon='+p.lon)).json();
   if(g.col!=null){drone=g;
     // 궤적: 위치가 유의미하게 바뀌면 점 추가
     const last=trail[trail.length-1];
     if(!last||Math.abs(last.col-g.col)+Math.abs(last.row-g.row)>=1){trail.push({col:g.col,row:g.row});if(trail.length>400)trail.shift();}
     draw();}
   if(tgt&&tgt.lat!=null){$('dist').textContent=Math.round(hav(p.lat,p.lon,tgt.lat,tgt.lon))+' m';}
 }}catch(e){}}
async function tickUgv(){try{const col=+$('col').value,row=+$('row').value;
  const u=await(await fetch('/api/ugv?col='+col+'&row='+row)).json();
  // 유닛 위경도→격자 정확 변환(서버 /api/cell)
  for(const un of (u.units||[])){const g=await(await fetch('/api/cell?lat='+un.lat+'&lon='+un.lon)).json();if(g.col!=null){un.col=g.col;un.row=g.row;}}
  for(const rt of (u.routes||[])){for(const p of rt.path){const g=await(await fetch('/api/cell?lat='+p.lat+'&lon='+p.lon)).json();if(g.col!=null){p.col=g.col;p.row=g.row;}}}
  // 경로가 바뀐 유닛은 주행 리셋
  (u.routes||[]).forEach(rt=>{const prev=(window.__ugv&&(window.__ugv.routes||[]).find(x=>x.id===rt.id));
    const changed=!prev||JSON.stringify(prev.path)!==JSON.stringify(rt.path);
    if(changed){_driveStart[rt.id]=null;_driveT[rt.id]=0;}});
  window.__ugv=u; draw();
  // 자원 목록 패널
  const rows=(u.units||[]).map(un=>{
    const rt=(u.routes||[]).find(r=>r.id===un.id)||{};
    const t=_driveT[un.id]||0;
    const icon=un.type==='FIRE_ENGINE'?'🚒':(un.type==='UGV'?'🚙':'🛩');
    const st=!rt.reachable?'<span style=color:#e88>도달불가</span>':(t>=0.999?'<span style=color:#8f8>도착</span>':('주행 '+Math.round(t*100)+'%'));
    const eta=rt.eta_sec!=null?(' · ETA '+Math.round(rt.eta_sec)+'s'):'';
    return '<div style="padding:3px 0;border-bottom:1px solid #22303f">'+icon+' '+un.id+' — '+st+eta+'</div>';
  }).join('');
  document.getElementById('fleet').innerHTML=rows||'<small>자원 없음</small>';
  // 도착한 자원의 목표 화재셀 진화 요청(중복 방지)
  (u.routes||[]).forEach(rt=>{ if(rt.reachable && (_driveT[rt.id]||0)>=0.999 && !_extd[rt.id]){
     _extd[rt.id]=true;
     fetch('/api/extinguish',{method:'POST',headers:{'Content-Type':'application/json'},
       body:JSON.stringify({col:+$('col').value,row:+$('row').value,resource_id:rt.id})})
       .then(r=>r.json()).then(d=>{ $('log').textContent = rt.id + (d && d.disabled
         ? ' 화재 지점 도착 (진화 효과 미반영 — 환경 모델 진화 기능 대기)'
         : ' 화재 도착 → 진화 반영 (시연 전용)'); }).catch(()=>{});if(window.__autoActive&&window.__autoActive()){window.__autoDone();_extd={};}
  }});
  const reach=(u.routes||[]).filter(r=>r.reachable).length, tot=(u.routes||[]).length;
  const eta=(u.routes||[]).map(r=>r.eta_sec).filter(x=>x!=null);
  $('ugvinfo').textContent='자원 '+tot+'대 · 도달 '+reach+'/'+tot+(eta.length?(' · ETA '+Math.round(Math.min(...eta))+'s'):'')+' · 차단도로 '+u.blocked_roads;
}catch(e){}}
function driveStep(){
  const U=window.__ugv; if(U){ (U.routes||[]).forEach(rt=>{
    if(rt.reachable&&rt.path&&rt.path.length>1){
      if(_driveStart[rt.id]==null)_driveStart[rt.id]=performance.now();
      const dur=Math.max(6,Math.min(60,(rt.eta_sec||30)))*1000; // 화면용 6~60s로 클램프
      _driveT[rt.id]=Math.min(1,(performance.now()-_driveStart[rt.id])/dur);
    }
  }); draw(); }
  requestAnimationFrame(driveStep);
}
requestAnimationFrame(driveStep);
async function tickModes(){try{const m=await(await fetch('/api/modes')).json();
 const e=$('mExt'); e.textContent=m.demo_extinguish?'진화 시연: 켜짐 (시연 전용)':'진화 시연: 꺼짐';
 e.className='badge'+(m.demo_extinguish?' on':''); e.title='WEB_DEMO_EXTINGUISH (서버 시작 시 결정, 화면에서 변경 불가)';
 const u=$('mUav'); u.textContent=m.uav_mode?('드론 서버: '+m.uav_mode+' ('+m.uav_id+')'):'드론 서버: 연결 안 됨';
 u.className='badge'+(m.uav_mode==='real'?' real':(m.uav_mode?'':' bad')); u.title=m.uav_agent;
 const d=$('mDisp'); d.textContent=m.dispatch_via_orch?'출동 경로: 총괄 경유':'출동 경로: 드론 직접';
 d.className='badge'+(m.dispatch_via_orch?' real':''); d.title='WEB_DISPATCH_VIA_ORCH (INT-01, 서버 시작 시 결정)';
 const k=$('mClock'); k.textContent=m.env_url?'산불 시계: 환경 서버 (읽기만)':'산불 시계: 관제판 자체';
 k.className='badge'+(m.env_url?' real':''); k.title=(m.env_url||'WEB_ENV_URL 미설정')+' · 거점 좌표: '+m.stations_source;
}catch(err){}}
setInterval(tickModes,10000);setTimeout(tickModes,300);
// INT-03 총괄 판단 요약 — 표기는 총괄 /board 와 같은 말을 쓴다. 불명·환경 반영 대기는 실패로 표시하지 않는다.
const O_PURPOSE={PENDING:['대기','wait'],HOLD:['보류','wait'],EVALUATING:['판단 중','go'],APPROVED:['출동 승인','go'],
 IN_EXECUTION:['출동 중','go'],COMPLETED:['완료','ok'],FAILED:['실패','fail'],CANCELLED:['취소','cancel'],UNKNOWN:['확인 필요','wait']};
const O_HOLD={AWAITING_PRIORITY_CHOICE:'사람 선택 대기',NO_FEASIBLE_CANDIDATE:'보낼 자원 없음',HUMAN_PRIORITY_CHOSEN:'사람이 선택함',
 EXECUTION_RESPONSE_LOST:'출동 응답 끊김',PROVIDER_LOST_TASK:'기체가 임무 기록 잃음',PROVIDER_OFFLINE:'기체 연락 두절',
 OBSERVATION_REQUIREMENT_NOT_MET:'관측 범위 부족 · 재관측 필요',ENV_APPLY_NOT_ACKED:'환경 반영 미확인',ARRIVED_OBSERVATION_PENDING:'도착 · 관측 대기',
 TARGET_LOCATION_UNKNOWN:'지도에 위치 없음 · 출동 보류',AREA_COVERAGE_INCOMPLETE:'구역 일부만 관측 · 남은 칸 대기',
 ENV_APPLY_TIMEOUT:'환경 반영 응답 없음',ENV_APPLY_PENDING:'관측 완료 · 환경 반영 확인 대기',RUN_GATE:'실행(run) 전환 대기',
 OPEN_ATTEMPT_EXISTS:'진행 중인 출동 있음',MANUAL_IDLE_CONFIRMED:'기체 정지 확인됨'};
const O_ATT={PREPARED:'출동 준비',REQUESTED:'출동 요청함',STARTED:'이동 중',ARRIVED:'도착',OBSERVED:'관측 완료',
 APPLIED:'환경 반영됨',RETURNING:'복귀 중',RELEASED:'반납 완료',UNKNOWN:'응답 확인 중',FAULTED:'기체 이상',NOT_SENT:'미전송'};
const O_KIND={ENV_SENSE:'환경 측정',RECON:'정찰',MONITOR:'감시',RECHECK:'재확인',GROUND_RECON:'지상 확인',GROUND_SUPPORT:'지상 지원'};
const O_MODE={AUTO_HIGHER_RISK:'자동 (AI 추천·규칙)',HUMAN_CHOICE:'수동 (사람이 선택)'};
function esc(s){return String(s==null?'':s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
async function tickOrch(){try{const o=await(await fetch('/api/orch')).json();
 $('orchLink').href=o.board_url||'#';
 const b=$('mOrch'); b.title=o.url;
 if(!o.connected){b.textContent='총괄 서버: 연결 안 됨';b.className='badge bad';$('mEnv').textContent='환경: -';$('orchMeta').textContent='-';$('orchTasks').innerHTML='';return;}
 b.textContent='총괄 서버: 연결됨';b.className='badge';
 const e=$('mEnv'); e.textContent=o.env_shared?'환경: 팀 공유':'환경: 시험용 ('+(o.env_class||'-')+')'; e.className='badge'+(o.env_shared?'':' on');
 $('orchMeta').textContent='판단 모드 '+(O_MODE[o.mode]||o.mode||'-')+' · 아는 불 '+o.fires+'곳 · 임무 '+o.tasks.length+'건'+(o.groups?' · 사람 선택 묶음 '+o.groups:'')+(o.llm_ready?'':' · AI 미사용(규칙)');
 $('orchTasks').innerHTML=o.tasks.length?o.tasks.map((t,i)=>{const p=O_PURPOSE[t.purpose_status]||[t.purpose_status||'-','wait'];
   const h=t.hold_reason?(O_HOLD[t.hold_reason.split(':')[0]]||'사유 기록됨'):'';
   return '<tr><td>'+(i+1)+'</td><td>'+esc(O_KIND[t.kind]||t.kind)+' '+esc(t.cell_id||'')+(h?'<div class=why>'+esc(h)+'</div>':'')+'</td>'
    +'<td><span class="st '+p[1]+'">'+esc(p[0])+'</span></td><td>'+esc(t.resource_id||'-')
    +(t.attempt?'<div class=why>'+esc(O_ATT[t.attempt]||t.attempt)+'</div>':'')+'</td></tr>';}).join('')
   :'<tr><td class=why>총괄이 아는 임무가 아직 없습니다 (신고·임무 접수 전)</td></tr>';
}catch(err){}}
setInterval(tickOrch,2000);setTimeout(tickOrch,500);
setInterval(tickEnv,1500);setInterval(tickState,1000);setInterval(tickUgv,3000);setTimeout(()=>{fit();tickEnv();tickState();tickUgv();},600);
$('fly').onclick=async()=>{const col=+$('col').value,row=+$('row').value;
 $('log').textContent='출동('+col+','+row+')…';
 const r=await(await fetch('/api/fly',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({col,row})})).json();
 if(r.via==='orch'){
   if(r.ok){tgt={col,row,lat:r.target.lat,lon:r.target.lon};
     const p=(O_PURPOSE[r.purpose_status]||[r.purpose_status||'-'])[0];
     const h=r.hold_reason?(' · '+(O_HOLD[r.hold_reason.split(':')[0]]||'사유 기록됨')):'';
     $('log').textContent='총괄에 출동 요청 접수 ('+(r.task_id||'-')+') · '+p+h+' — 진행은 아래 총괄 판단에서 확인';}
   else{$('log').textContent='⛔ 총괄 출동 요청 실패: '+(r.reason||'');}
   draw();return;}
 if(r.ok){tgt={col,row,lat:r.target.lat,lon:r.target.lon};trail=[];_driveT={};_driveStart={};_extd={};
   $('log').textContent='✅ ACCEPT\\n타깃 '+JSON.stringify(r.target)+'\\ntask '+r.task_id;}
 else{$('log').textContent='⛔ '+(r.verdict||'')+' '+(r.reason||'');}
 draw();};
$('clr').onclick=()=>{trail=[];draw();};
</script><script src="/static/auto.js"></script></body></html>"""