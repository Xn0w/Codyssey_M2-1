"""UAV 1대·UGV 1대 PX4·Gazebo 실기동 통합 (총괄 경유). 명시적 실기동 프로파일 — mock·sim 없음, 실시간 배율 1.

    python integration/px4_live/run_integ.py preflight            # 사전 점검만 (포트·버전·코드·월드·DEM·도로망 해시)
    python integration/px4_live/run_integ.py run --minutes 30     # 전체 실행 (끝나면 이 도구가 띄운 것만 끈다)
    python integration/px4_live/run_integ.py stop                 # 긴급 종료: 이 도구가 띄운 것만 (pid 기록 기준)

구성 (PROFILE): 같은 Gazebo 월드(트윈 지형 타일 구역 tz_a33)에 x500(PX4 인스턴스 0, UAV A-uav1)·adair_ugv(인스턴스 1, UGV A-ugv1)
  환경 계약 서버 :8300 (2019 인제 트윈 설정, 시험 발화점 칸 46_48 — 명시적 시험 사건), 트윈 시계 실시간(배율 1, LLM 대기 멈춤 끔)
  UGV 서버 :8100 (px4 드라이버, 시험 훅 없음, 환경 화재 자료), UAV 에이전트 :8000 (real, PX4 udpin 14540)
  총괄 :8200 (team_http 환경, 등록 = 실제 띄운 A-uav1 만, UGV 는 서버의 A-ugv1 만, UGV 복귀 총괄 관리, 관측 계획 LLM 끔 → 규칙 판단)
  운용자 (이 스크립트): 총괄이 불을 '확인'하면 그 칸 지상 지원(GROUND_SUPPORT, UGV)을 요청만 한다 — 차량 선택·Safety 는 총괄
기록: logs/integ/run_<시각>/ (profile.json, preflight.json, timeline.jsonl, track_*.csv, 서버 로그, 총괄 DB, 환경 상태)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
WSL = ["wsl.exe", "-d", "Ubuntu-24.04", "--"]
PIDS = ROOT / "logs" / "integ" / "running.json"

PROFILE = {
    "world": "tz_a33", "gz_partition": "adair_integ", "wsl_state": "~/.adair-integ",
    "spawn": ["0 x500 4022.33,5570.69,27.05,0 A-uav1",              # 인제119 좌표 (UAV 에이전트 A 기지·PX4 home 과 같게), 충돌면 +0.15 m
              "1 adair_ugv 4130.88,5675.67,26.273,0.7521 A-ugv1"],    # UGV 대기 지점 (logs/ugv/stage4/tz_a33_spawn_ugv.txt)
    "env": {"ENV_CONFIG": "environment/config/scenario_whatif_2019_legacy.yaml", "ENV_SEED": "9", "ENV_TICK_S": "2100",
            "ENV_SUBTICK_S": "60", "ENV_SCENARIO_START_KST": "2019-04-04T14:45:00+09:00", "ENV_IGNITION": "46,48",
            "ENV_REPORT_DELAY_S": "60", "ENV_RESUME": "0"},
    "ugv": {"UGV_DRIVER": "px4", "UGV_VEHICLES_JSON": "logs/ugv/stage4/single_a_fleet.json",
            "UGV_ROAD_SUBSET": "logs/ugv/stage5/tiles/road_subset_tz_a33.json", "UGV_ENV_URL": "http://127.0.0.1:8300",
            "UGV_TIME_SCALE": "1"},
    "uav": {"UAV_ID": "A-uav1", "UAV_MODE": "real", "PX4_ADDRESS": "udpin://0.0.0.0:14540"},
    "orch": {"ORCH_ENV_MODE": "team_http", "ORCH_ENV_URL": "http://127.0.0.1:8300", "ORCH_UAV_ENDPOINTS_REPLACE": "1",
             "ORCH_UAV_ENDPOINTS": "A-uav1=http://127.0.0.1:8000", "ORCH_UGV_RETURN_HOME": "1", "ORCH_OBS_PLANNER": "0",
             "ORCH_PREEMPTIVE_MONITOR": "0", "ORCH_AUTO_RECON_GROUND": "0"},
    "clock": ["--speed", "1", "--no-llm-pause"],
    "operator_ground_types": ["UGV"],
}
PORTS = {"uav": 8000, "ugv": 8100, "orch": 8200, "env": 8300}
UGV_URL = "http://127.0.0.1:8100"


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def wslpath(p: Path) -> str:
    from ugv.tools.drive_test import to_wsl_path
    return to_wsl_path(p)


def port_owner(port):
    out = sh(["netstat", "-ano", "-p", "TCP"]).stdout
    for ln in out.splitlines():
        f = ln.split()
        if len(f) >= 5 and f[1].endswith(f":{port}") and f[3] == "LISTENING":
            return int(f[4])
    return None


def preflight(run: Path) -> dict:
    from ugv import version
    rep = {"time_local": time.strftime("%F %T"), "code": version.code_info(), "ports": {}, "problems": []}
    for name, p in PORTS.items():
        owner = port_owner(p)
        rep["ports"][name] = {"port": p, "listening_pid": owner}
        if owner:
            rep["problems"].append(f"포트 {p} ({name}) 사용 중 pid {owner} — 다른 시험·사용자 프로세스일 수 있어 끄지 않는다")
    v = sh(WSL + ["bash", "-lc", "cd ~/PX4-Autopilot && git describe --tags; gz sim --version | head -1; "
                                 "ls ~/PX4-Autopilot/build/px4_sitl_default/bin/px4"]).stdout.strip().splitlines()
    rep["px4_gz"] = v
    import importlib.metadata as md
    rep["mavsdk_python"] = md.version("mavsdk")
    tiles = ROOT / "logs" / "ugv" / "stage5" / "tiles"
    rep["world_sdf_sha1"] = version.file_sha1(str(tiles / f"{PROFILE['world']}.sdf"))
    rep["dem_sha1"] = version.file_sha1(str(ROOT / "environment" / "data" / "processed" / "dem_clipped.tif"))
    rep["road_subset_sha1"] = version.file_sha1(str(ROOT / PROFILE["ugv"]["UGV_ROAD_SUBSET"]))
    rep["tiles_meta_sha1"] = version.file_sha1(str(tiles / "tiles.json"))
    rep["llm_key_present"] = bool(os.getenv("OPENAI_API_KEY"))          # 값은 기록하지 않는다
    (run / "preflight.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


class Procs:
    def __init__(self, run: Path):
        self.run, self.p = run, {}

    def start(self, name, cmd, env_extra, cwd=ROOT):
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", **env_extra}
        log = open(self.run / f"{name}.log", "w", encoding="utf-8")
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        self.p[name] = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        self.save()
        return self.p[name]

    def save(self):
        PIDS.write_text(json.dumps({"run": str(self.run), "pids": {k: v.pid for k, v in self.p.items()}}), encoding="utf-8")

    def stop_all(self):
        for name, pr in reversed(list(self.p.items())):
            if pr.poll() is None:
                sh(["taskkill", "/F", "/T", "/PID", str(pr.pid)])


def wait_http(url, timeout=120):
    import httpx
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if httpx.get(url, timeout=5).status_code < 500:
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    return False


def stop_cmd():
    if PIDS.exists():
        d = json.loads(PIDS.read_text(encoding="utf-8"))
        for name, pid in d["pids"].items():
            sh(["taskkill", "/F", "/T", "/PID", str(pid)])
            print("종료", name, pid)
    st = PROFILE["wsl_state"].replace("~", "$HOME")
    print(sh(WSL + ["bash", "-lc", f"STATE={st} bash {wslpath(ROOT / 'integration/px4_live/wsl_stop.sh')} --params"]).stdout)


def run_cmd(minutes: float, run: Path, pretest: bool = False, dry: bool = False):
    """dry: Gazebo·PX4 없이 총괄 흐름만 점검 (UGV sim 드라이버 :8102, UAV mock 실시간). 실제 시연 결과로 세지 않는다."""
    import httpx
    global UGV_URL
    if dry:
        UGV_URL = "http://127.0.0.1:8102"
        PORTS["ugv"] = 8102
    rep = preflight(run)
    (run / "profile.json").write_text(json.dumps({**PROFILE, "mode": "dry" if dry else ("pretest" if pretest else "run")}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    if rep["problems"]:
        print("사전 점검 문제 — 실행하지 않는다:", rep["problems"])
        return
    procs = Procs(run)
    try:
        # 1) Gazebo 월드 + PX4 2대 (WSL) — dry 는 건너뜀
        spawn = run / "spawn.txt"
        if dry:
            spawn.write_text("", encoding="utf-8")
        spawn.write_text("\n".join(PROFILE["spawn"]) + "\n", encoding="utf-8")
        st = PROFILE["wsl_state"].replace("~", "$HOME")
        if not dry:
          sh(WSL + ["bash", "-lc", f"STATE={st} bash {wslpath(ROOT / 'integration/px4_live/wsl_stop.sh')} --params"])
          out = sh(WSL + ["bash", "-lc", f"cd {wslpath(ROOT)} && WORLD={PROFILE['world']} PART={PROFILE['gz_partition']} "
                                       f"STATE={st} bash integration/px4_live/wsl_world.sh {wslpath(spawn)}"])
          (run / "wsl_world.log").write_text(out.stdout + out.stderr, encoding="utf-8")
          print(out.stdout[-600:], flush=True)
        # 2) 환경 서버
        procs.start("env", [PY, "-m", "uvicorn", "environment.server:app", "--host", "127.0.0.1", "--port", "8300",
                            "--log-level", "warning"], {**PROFILE["env"], "ENV_STATE_DIR": str(run / "env")})
        assert wait_http("http://127.0.0.1:8300/health", 180), "환경 서버 기동 실패"
        # 3) UGV 서버 (px4) · UAV 에이전트 (real)
        ugv_env = {**{k: (str(ROOT / v) if k in ("UGV_VEHICLES_JSON", "UGV_ROAD_SUBSET") else v) for k, v in PROFILE["ugv"].items()},
                   "UGV_STATE_DIR": str(run / "ugv")}
        uav_env = {**PROFILE["uav"], "UAV_STATE_DIR": str(run / "uav")}
        if dry:
            fl = json.loads((ROOT / PROFILE["ugv"]["UGV_VEHICLES_JSON"]).read_text(encoding="utf-8"))
            (run / "fleet_sim.json").write_text(json.dumps([{**c, "driver": "sim"} for c in fl]), encoding="utf-8")
            ugv_env.update(UGV_DRIVER="sim", UGV_VEHICLES_JSON=str(run / "fleet_sim.json"))
            uav_env.update(UAV_MODE="mock", UAV_MOCK_TIME_SCALE="1")
        procs.start("ugv", [PY, "-m", "uvicorn", "ugv.server:app", "--host", "127.0.0.1", "--port", str(PORTS["ugv"])], ugv_env)
        procs.start("uav", [PY, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"], uav_env,
                    cwd=ROOT / "uav" / "uav-agent")
        assert wait_http("http://127.0.0.1:8000/health", 120), "UAV 에이전트 기동 실패"
        t0 = time.time()
        while time.time() - t0 < 180:            # UGV 차량 READY (PX4 연결·텔레메트리) 대기
            try:
                if any(s["state"] == "READY" for s in httpx.get(UGV_URL + "/ugv", timeout=5,
                                                               headers={"X-ADAIR-Monitor": "1"}).json()):
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2)
        if pretest:
            pretest_direct(run, minutes)
            return
        # 4) 총괄
        procs.start("orch", [PY, "-m", "orchestrator.api"], {**PROFILE["orch"], "ORCH_DB_PATH": str(run / "orch.sqlite3"),
                                                              "ORCH_UGV_SERVER_URL": UGV_URL})
        assert wait_http("http://127.0.0.1:8200/health", 120), "총괄 기동 실패"
        # 5) Gazebo 궤적 기록
        from ugv.tools.drive_test import WSL_DISTRO
        trk = []
        for model in (() if dry else ("x500_0", "adair_ugv_1")):
            trk.append(subprocess.Popen(["wsl.exe", "-d", WSL_DISTRO, "--", "env", f"GZ_PARTITION={PROFILE['gz_partition']}",
                                         "GZ_IP=127.0.0.1", "python3", wslpath(ROOT / "ugv" / "tools" / "gz_track.py"),
                                         "--world", PROFILE["world"], "--model", model, "--out", wslpath(run / f"track_{model}.csv"),
                                         "--duration", str(minutes * 60 + 120)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        # 6) 시계 (실시간) — 시작 시각 기록
        procs.start("clock", [PY, "tools/twin_clock.py", "--env", "http://127.0.0.1:8300", "--orch", "http://127.0.0.1:8200",
                              *PROFILE["clock"]], {})
        start_wall = time.time()
        print(f"시작 {time.strftime('%T')} — 총괄 경유 운용 (최대 {minutes} 분)", flush=True)
        record(run, start_wall, minutes)
    finally:
        procs.stop_all()
        for t in locals().get("trk", []):
            t.terminate()
        st = PROFILE["wsl_state"].replace("~", "$HOME")
        if not dry:
            sh(WSL + ["bash", "-lc", f"STATE={st} bash {wslpath(ROOT / 'integration/px4_live/wsl_stop.sh')}"])
        # PX4 ULog 복사 (인스턴스 0·1 의 마지막 로그)
        sh(WSL + ["bash", "-lc", f"mkdir -p {wslpath(run / 'ulog')} && for i in 0 1; do f=$(ls -t {st}/px4-$i/log/*/*.ulg 2>/dev/null | head -1); "
                                 f"[ -n \"$f\" ] && cp \"$f\" {wslpath(run / 'ulog')}/px4-$i.ulg; cp {st}/px4-$i.log {wslpath(run / 'ulog')}/ 2>/dev/null; done"])
        print("종료·기록:", run)


def pretest_direct(run: Path, minutes: float):
    """시연 경로 사전 시험 (총괄 없음 — 개별 동작 확인): UGV 를 시험 화재로 접근시켰다가 거점 복귀, 동시에 UAV 를 화재 위 관측 후 복귀·착륙.
    같은 월드·환경·서버 구성 (통합과 동일). 판정은 analyze_pretest."""
    import httpx
    import gz_bridge as gb
    from ugv.tools.drive_test import WSL_DISTRO
    col, row = (int(v) for v in PROFILE["env"]["ENV_IGNITION"].split(","))
    la, lo = gb.grid_cell_to_latlon(col, row)
    trk = [subprocess.Popen(["wsl.exe", "-d", WSL_DISTRO, "--", "env", f"GZ_PARTITION={PROFILE['gz_partition']}", "GZ_IP=127.0.0.1",
                             "python3", wslpath(ROOT / "ugv" / "tools" / "gz_track.py"), "--world", PROFILE["world"], "--model", "adair_ugv_1",
                             "--out", wslpath(run / "track_adair_ugv_1.csv"), "--duration", str(minutes * 60 + 60)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)]
    uav = subprocess.Popen([PY, "integration/px4_live/uav_pretest.py", "--tag", f"{run.name}_uav", "--target", str(la), str(lo),
                            "--observe", "60", "--timeout-s", str(minutes * 60)], cwd=str(ROOT),
                           env={**os.environ, "PYTHONIOENCODING": "utf-8", "INTEG_WORLD": PROFILE["world"],
                                "INTEG_PARTITION": PROFILE["gz_partition"]},
                           stdout=open(run / "uav_pretest.out", "w", encoding="utf-8"), stderr=subprocess.STDOUT)
    c = httpx.Client(base_url=UGV_URL, timeout=60)
    log = {"fire": {"cell": f"{col}_{row}", "lat": la, "lon": lo}, "ugv": []}
    body = {"task_id": "PRE-UGV-FIRE", "decision_id": "D-PRE-UGV-FIRE", "target": {"lat": la, "lon": lo}}
    ev = c.post("/ugv/A-ugv1/evaluate", json=body).json()
    log["evaluate"] = ev
    print("UGV evaluate", ev.get("verdict"), ev.get("eta_sec"), ev.get("reason"), flush=True)
    t0 = time.time()
    if ev.get("verdict") == "ACCEPT":
        r = c.post("/ugv/A-ugv1/execute", json={**body, "target_node": ev["target_node"]["node_id"]})
        log["execute"] = r.json()
        for key in ("PRE-UGV-FIRE", "PRE-UGV-HOME"):
            if key == "PRE-UGV-HOME":
                st = c.get("/ugv/A-ugv1/state").json()
                acc = st["station"]["access_point"]
                r = c.post("/ugv/A-ugv1/execute", json={"task_id": key, "decision_id": "D-" + key,
                                                         "target_node": f"RP:{acc['road_id']}:{acc['s_m']:.1f}"})
                log["execute_home"] = r.json()
            while time.time() - t0 < minutes * 60:
                t = c.get(f"/ugv/A-ugv1/task/{key}").json()
                s = c.get("/ugv/A-ugv1/state").json()
                log["ugv"].append({"t": round(time.time() - t0, 1), "key": key, "status": t.get("status"), "state": s["state"],
                                   "mission": s["mission_state"], "speed": s["speed_mps"], "pos": s["position"]})
                if t.get("status") in ("COMPLETED", "FAILED", "CANCELLED") and s["state"] == "READY":
                    print(f"[{time.time() - t0:6.1f}] UGV {key} {t.get('status')} {t.get('error') or ''}", flush=True)
                    log[f"task_{key}"] = t
                    break
                time.sleep(2)
            time.sleep(20)                                  # 도착 뒤 대기
    uav.wait(timeout=max(60, minutes * 60 - (time.time() - t0)))
    for p in trk:
        p.terminate()
    log["analysis_ugv"] = analyze_ugv(run / "track_adair_ugv_1.csv", la, lo)
    (run / "pretest.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(log["analysis_ugv"], ensure_ascii=False), flush=True)


def analyze_ugv(csv_path: Path, fire_lat, fire_lon):
    """UGV Gazebo 궤적: 차체 이탈(원시 표본 전부, coverage_judge 와 같은 기준), 화재 칸 경계까지 최소 거리, 지나간 도로."""
    from ugv.geo import GZ_FRAME, FRAME
    from ugv.profiles import get
    from ugv.roads import RoadNetwork
    from ugv.tools import coverage_judge as CJ
    from ugv.tools.drive_test import load_track
    import math
    if not csv_path.exists():
        return {"status": "INCOMPLETE", "why": "궤적 없음"}
    rows = load_track(csv_path)
    if len(rows) < 20:
        return {"status": "INCOMPLETE", "why": f"표본 {len(rows)}"}
    net = RoadNetwork()
    P = get("adair_ugv")
    full, bad, roll, n, gap = CJ.scan(net, net.graph_for(P), P, rows)
    fx, fy = FRAME.to_xy(fire_lat, fire_lon)
    dmin = min(max(math.dist((r["x"], r["y"]), (fx, fy)) - 45.0 * math.sqrt(2), 0.0) for r in rows)
    return {"status": "OK", "samples": n, "pose_gap_max_s": round(gap, 2), "offroad_samples": len(bad),
            "offroad_max_m": round(max((b[2] for b in bad), default=0.0), 3), "rollover_samples": len(roll),
            "roads_driven": sorted(r for r, fr in full.items() if fr >= CJ.COVER_MIN),
            "min_dist_to_fire_cell_m_conservative": round(dmin, 1),
            "basis": "화재 칸 경계 거리 = 칸 중심 거리 − 칸 반대각선(63.6 m, 보수적). 궤적 좌표 = Gazebo 월드(GZ) ≈ 지역 평면(0.1~0.2 m 차)"}


def record(run: Path, start_wall: float, minutes: float):
    """2 s 마다 총괄·환경·UGV 상태, UAV 상태(조회가 느려 별도 스레드), 운용자 지상 지원 요청. 끝 조건: 두 자원 모두 반납 + 30 s, 또는 시간."""
    import httpx
    mon = {"X-ADAIR-Monitor": "1"}
    cx = httpx.Client(timeout=20)
    f = open(run / "timeline.jsonl", "a", encoding="utf-8")
    uav_last = {}

    def uav_loop():
        while not stop.is_set():
            try:
                uav_last.update(httpx.get("http://127.0.0.1:8000/uav/A-uav1/state", timeout=30).json(), _wall=time.time())
            except Exception as e:  # noqa: BLE001
                uav_last.update({"_error": str(e)[:120], "_wall": time.time()})
            time.sleep(1)
    stop = threading.Event()
    th = threading.Thread(target=uav_loop, daemon=True)
    th.start()
    requested = set()
    done_since = None
    while time.time() - start_wall < minutes * 60:
        rec = {"t": round(time.time() - start_wall, 1), "wall": time.time()}
        try:
            snap = cx.get("http://127.0.0.1:8300/snapshot").json()
            rec["env"] = {"t": snap["simulation_time_s"], "ver": snap["state_version"], "run": snap["run_id"],
                          "fires": [(c["cell_id"], c["fire_state"]) for c in snap.get("fire_cells", [])][:10]}
        except Exception as e:  # noqa: BLE001
            rec["env_error"] = str(e)[:120]
        try:
            rec["ugv"] = [{k: s.get(k) for k in ("resource_id", "state", "mission_state", "speed_mps", "current_task_id", "fault",
                                                 "position", "heading_deg", "updated_at")}
                          for s in cx.get(UGV_URL + "/ugv", headers=mon).json()]
        except Exception as e:  # noqa: BLE001
            rec["ugv_error"] = str(e)[:120]
        rec["uav"] = {k: uav_last.get(k) for k in ("position", "velocity_ms", "armed", "flight_mode", "battery", "current_task_id",
                                                   "returning_task_id", "_wall", "_error")}
        try:
            st = cx.get("http://127.0.0.1:8200/state").json()
            import sqlite3
            con = sqlite3.connect(f"file:{run / 'orch.sqlite3'}?mode=ro", uri=True, timeout=5)
            atts_db = [dict(zip(("attempt_id", "task_id", "resource_id", "substatus"), r))
                       for r in con.execute("select attempt_id, task_id, resource_id, substatus from attempts order by rowid")]
            con.close()
            rec["orch"] = {"reservations": st.get("reservations"), "attempts": atts_db, "tasks": st.get("tasks"),
                           "holds": st.get("holds")}
            board = cx.get("http://127.0.0.1:8200/priority/board").json()
            fires = [x for x in (board.get("known") or {}).get("fires", []) if str(x.get("status", "")).startswith("CONFIRMED")]
            rec["confirmed_fires"] = [x.get("cell_id") for x in fires]
            for fz in fires:
                cid = fz.get("cell_id")
                if cid in requested:
                    continue
                cell = next((c for c in cx.get("http://127.0.0.1:8300/map_cells").json()["cells"] if c["cell_id"] == cid), None)
                if cell is None:
                    continue
                body = {"request_id": f"OPERATOR-GROUND:{rec.get('env', {}).get('run')}:{cid}", "incident_id": "INC-INTEG-TEST",
                        "kind": "GROUND_SUPPORT", "target": {k: cell[k] for k in ("lat", "lon", "ground_amsl_m", "cell_id")},
                        "requirements": {"resource_types": PROFILE["operator_ground_types"], "sensor": None, "needs_env_ack": False}}
                r = cx.post("http://127.0.0.1:8200/tasks", json=body)
                rec["operator_request"] = {"cell": cid, "code": r.status_code, "body": r.json() if r.status_code < 500 else r.text[:200]}
                print(f"[{rec['t']:7.1f}] 운용자: 불 확인 {cid} → 지상 지원 요청 HTTP {r.status_code}", flush=True)
                requested.add(cid)
        except Exception as e:  # noqa: BLE001
            rec["orch_error"] = str(e)[:160]
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        atts = (rec.get("orch") or {}).get("attempts") or []
        uav_rel = any(a["resource_id"] == "A-uav1" and a["substatus"] == "RELEASED" for a in atts)
        ugv_rel = any(a["resource_id"] == "A-ugv1" and a["substatus"] == "RELEASED" for a in atts)
        open_ = [a for a in atts if a["substatus"] not in ("RELEASED", "FAILED", "CANCELLED")]
        if int(rec["t"]) % 30 == 0:
            print(f"[{rec['t']:7.1f}] 시도 {[(a['resource_id'], a['substatus']) for a in atts]} 불확인 {rec.get('confirmed_fires')}", flush=True)
        if uav_rel and ugv_rel and not open_:
            done_since = done_since or time.time()
            if time.time() - done_since > 30:
                print(f"[{rec['t']:7.1f}] 두 자원 반납 확인 — 정상 종료", flush=True)
                break
        time.sleep(2)
    stop.set()
    for name in ("orch_final", "ugv_final", "uav_final"):
        try:
            url = {"orch_final": "http://127.0.0.1:8200/state", "ugv_final": UGV_URL + "/ugv",
                   "uav_final": "http://127.0.0.1:8000/uav/A-uav1/state"}[name]
            (run / f"{name}.json").write_text(json.dumps(cx.get(url, headers=mon, timeout=40).json(), ensure_ascii=False, indent=1),
                                              encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            (run / f"{name}.json").write_text(json.dumps({"error": str(e)}), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("preflight", "pretest", "run", "stop"))
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--ugv-lat-accel", type=float, default=None,
                    help="UGV 곡선 횡가속 한도 m/s² (기본 1.5). 지형 월드 회전 이탈 완화 시험값 — 프로파일 기록에 남는다")
    ap.add_argument("--llm-planner", action="store_true", help="총괄 관측 계획 LLM 켬 (ADAIR .env 키, 기본 끔 = 규칙 판단)")
    ap.add_argument("--dry", action="store_true", help="Gazebo·PX4 없이 총괄 흐름만 (UGV sim, UAV mock 실시간) — 실제 시연 아님")
    a = ap.parse_args()
    if a.cmd == "stop":
        stop_cmd()
        return
    run = ROOT / "logs" / "integ" / f"{'dry' if a.dry else a.cmd}_{time.strftime('%Y%m%d_%H%M%S')}"
    run.mkdir(parents=True, exist_ok=True)
    if a.cmd == "preflight":
        print(json.dumps(preflight(run), ensure_ascii=False, indent=1))
        return
    if a.llm_planner:
        PROFILE["orch"]["ORCH_OBS_PLANNER"] = "1"
    if a.ugv_lat_accel is not None:
        PROFILE["ugv"]["UGV_LAT_ACCEL"] = str(a.ugv_lat_accel)
    run_cmd(a.minutes, run, pretest=(a.cmd == "pretest"), dry=a.dry)


if __name__ == "__main__":
    main()
