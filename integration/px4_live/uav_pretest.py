"""UAV 1대 PX4·Gazebo 사전 시험 (UAV 에이전트 HTTP 를 직접 — 총괄 경유 아님, 개별 동작 확인용).

  python integration/px4_live/uav_pretest.py --tag p1_mission --target 38.0711 128.1722 --observe 30
  python integration/px4_live/uav_pretest.py --tag p2_abort --target ... --abort-after-s 40      # 비행 중 취소 → 복귀
  python integration/px4_live/uav_pretest.py --tag p3_dup --target ... --duplicate                # 같은 실행 키 재전송
  python integration/px4_live/uav_pretest.py --tag p4_link --target ... --link-cut-s 20           # (WSL PX4 링크 끊기) 단절
기록: logs/integ/<tag>/ — run.json (요청·응답·1 s 상태·판정), track.csv (Gazebo 실제 자세 x500_0)
판정 (원시 기록에서): 실제 이륙·목표 도착(수평 10 m·고도 10 m)·관측 체류·복귀·착륙·시동 해제, 지형 여유(충돌면·원본 DEM),
실제 속도·상승하강률, 착륙 확인 전 READY 여부, 실행 경로 식별(route_id/hash)과 평가 응답 일치.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

AGENT = os.getenv("UAV_AGENT_URL", "http://127.0.0.1:8000")
RID = os.getenv("UAV_ID", "A-uav1")
WORLD = os.getenv("INTEG_WORLD", "tz_a33")
PART = os.getenv("INTEG_PARTITION", "adair_integ")
DATUM_ELEV = 172.1                     # 타일 월드 spherical_coordinates elevation (z=0 의 해발)


def start_track(out, dur):
    from ugv.tools.drive_test import to_wsl_path, WSL_DISTRO
    cmd = ["wsl.exe", "-d", WSL_DISTRO, "--", "env", f"GZ_PARTITION={PART}", "GZ_IP=127.0.0.1", "python3",
           to_wsl_path(ROOT / "ugv" / "tools" / "gz_track.py"), "--world", WORLD, "--model", "x500_0",
           "--out", to_wsl_path(out), "--duration", str(dur)]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def link(act):
    from ugv.tools.drive_test import to_wsl_path
    subprocess.run(["wsl.exe", "-d", "Ubuntu-24.04", "--", "bash", to_wsl_path(ROOT / "integration" / "px4_live" / "wsl_link.sh"),
                    "0", act], check=False)


def analyze(track_csv, polls, home_ll, target_ll):
    from ugv.geo import GZ_FRAME, FRAME
    from ugv.tools import build_terrain_tiles as BT
    from ugv.tools.drive_test import load_track
    import numpy as np
    rows = load_track(track_csv) if Path(track_csv).exists() else []
    if len(rows) < 10:
        return {"status": "INCOMPLETE", "why": f"Gazebo 궤적 {len(rows)} 표본"}
    S = BT.Surface()
    F = BT.Fields()
    hx, hy = FRAME.to_xy(*home_ll)
    tx, ty = FRAME.to_xy(*target_ll)
    out, clear, clear_dem, vs, hs = [], [], [], [], []
    prev = None
    for r in rows[::5]:
        la, lo = GZ_FRAME.to_ll(r["x"], r["y"])
        x, y = FRAME.to_xy(la, lo)
        z = r["z"] + DATUM_ELEV
        zs = S.z(x, y)
        E, N = BT.to5186_exact(x, y)
        zd = float(F.dem(np.array([E]), np.array([N]), clamp=True)[0])
        away = math.dist((x, y), (hx, hy)) > 30.0          # 이착륙장 주변(30 m)은 지형 여유 판정에서 뺀다
        if away and not math.isnan(zs):
            clear.append(z - zs)
            clear_dem.append(z - zd)
        if prev is not None:
            dt = r["sim_t"] - prev[0]
            if dt > 0:
                hs.append(math.dist((x, y), prev[1]) / dt)
                vs.append((z - prev[2]) / dt)
        prev = (r["sim_t"], (x, y), z)
        out.append((r["sim_t"], x, y, z, zs))
    # 목표 도착: 수평 10 m 안 표본
    near_t = [o[0] for o in out if math.dist(o[1:3], (tx, ty)) <= 10.0]
    # 직선 경로(기지→목표) 횡오차 (순항 구간: 기지·목표 50 m 밖)
    L = math.dist((hx, hy), (tx, ty))
    ux, uy = (tx - hx) / L, (ty - hy) / L
    xt = [abs((o[1] - hx) * uy - (o[2] - hy) * ux) for o in out
          if math.dist(o[1:3], (hx, hy)) > 50 and math.dist(o[1:3], (tx, ty)) > 50]
    final = out[-1]
    return {"status": "OK", "samples": len(rows), "sim_s": round(rows[-1]["sim_t"] - rows[0]["sim_t"], 1),
            "min_clearance_surface_m": round(min(clear), 1) if clear else None,
            "min_clearance_dem_m": round(min(clear_dem), 1) if clear_dem else None,
            "max_alt_amsl_m": round(max(o[3] for o in out), 1),
            "max_hspeed_mps": round(max(hs), 2) if hs else None,
            "cruise_hspeed_p50_mps": round(sorted(h for h in hs if h > 2)[len([h for h in hs if h > 2]) // 2], 2) if any(h > 2 for h in hs) else None,
            "max_climb_mps": round(max(vs), 2) if vs else None, "max_descent_mps": round(-min(vs), 2) if vs else None,
            "target_reached_sim_t": near_t[0] if near_t else None, "time_within_10m_of_target_s": round(len(near_t) * 5 * (rows[1]["sim_t"] - rows[0]["sim_t"]), 1) if near_t else 0.0,
            "cruise_cross_track_p95_m": round(sorted(xt)[int(0.95 * (len(xt) - 1))], 1) if xt else None,
            "final_dist_to_home_m": round(math.dist(final[1:3], (hx, hy)), 1),
            "final_height_above_surface_m": round(final[3] - final[4], 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--target", nargs=2, type=float, required=True)
    ap.add_argument("--observe", type=int, default=30)
    ap.add_argument("--wind", type=float, default=3.0)
    ap.add_argument("--abort-after-s", type=float, default=None)
    ap.add_argument("--duplicate", action="store_true")
    ap.add_argument("--link-cut-s", type=float, default=None, help="이륙 뒤 N 초에 WSL PX4 인스턴스 0 MAVLink 를 끊었다가 30 s 뒤 복구")
    ap.add_argument("--timeout-s", type=float, default=1500)
    a = ap.parse_args()
    out_dir = ROOT / "logs" / "integ" / a.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    c = httpx.Client(base_url=AGENT, timeout=60)
    log = {"tag": a.tag, "start_local": time.strftime("%F %T"), "agent": AGENT, "rid": RID,
           "health": c.get("/health").json(), "state0": c.get(f"/uav/{RID}/state").json(), "polls": [], "events": []}
    from ugv import version
    log["tool_code"] = version.code_info()
    home = (log["state0"]["position"]["lat"], log["state0"]["position"]["lon"])
    trk = start_track(out_dir / "track.csv", a.timeout_s + 60)
    time.sleep(3)
    key = f"PRE-{a.tag}-{time.strftime('%H%M%S')}"
    from ugv.geo import FRAME
    from ugv.terrain.dem import z_at
    gz = z_at(*FRAME.to_xy(*a.target))          # 목표 지면 해발고도 = 환경 DEM (총괄이 넣는 값과 같은 출처)
    log["target_ground_amsl_dem"] = gz
    body = {"task_id": key, "decision_id": "D-" + key, "target": {"lat": a.target[0], "lon": a.target[1], "alt_m_amsl": gz},
            "observation_type": "THERMAL", "observe_duration_s": a.observe, "wind_ms": a.wind}
    ev = c.post(f"/uav/{RID}/evaluate", json=body).json()
    log["evaluate"] = ev
    print("evaluate", ev.get("verdict"), ev.get("eta_sec"), ev.get("reason"), flush=True)
    if ev.get("verdict") != "ACCEPT":
        log["result"] = "EVALUATE_NOT_ACCEPT"
        (out_dir / "run.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
        trk.terminate()
        return
    xb = {k: v for k, v in body.items() if k != "wind_ms"}
    xb.update({"route_id": ev.get("route_id"), "route_hash": ev.get("route_hash")})
    t0 = time.time()
    r = c.post(f"/uav/{RID}/execute", json=xb)
    log["execute"] = {"code": r.status_code, "body": r.json()}
    print("execute", r.status_code, r.json().get("status"), flush=True)
    if a.duplicate:
        time.sleep(5)
        r2 = c.post(f"/uav/{RID}/execute", json=xb)
        log["execute_duplicate"] = {"code": r2.status_code, "body": r2.json()}
        print("duplicate", r2.status_code, r2.json(), flush=True)
    aborted = link_cut = link_back = None
    ready_before_landed = 0
    while time.time() - t0 < a.timeout_s:
        # 링크 복구는 조회 성공과 관계없이 벽시계로 (끊긴 동안 조회가 계속 실패한다)
        if link_cut is not None and link_back is None and time.time() - t0 >= link_cut + 30:
            link("start")
            link_back = round(time.time() - t0, 1)
            log["link_back"] = link_back
            print("link back", flush=True)
        try:
            st = c.get(f"/uav/{RID}/state").json()
            tk = c.get(f"/uav/{RID}/task/{key}").json()
        except Exception as e:  # noqa: BLE001
            log["polls"].append({"t": round(time.time() - t0, 1), "error": str(e)[:200]})
            time.sleep(1)
            continue
        p = {"t": round(time.time() - t0, 1), "lat": st["position"]["lat"], "lon": st["position"]["lon"],
             "alt_amsl": st["position"]["alt_m_amsl"], "alt_rel": st["position"]["alt_m_agl"], "v": st.get("velocity_ms"),
             "armed": st.get("armed"), "mode": st.get("flight_mode"), "bat": st["battery"]["percent"],
             "status": tk.get("status"), "phys": tk.get("physical_state"), "phase": (tk.get("progress") or {}).get("phase"),
             "result": tk.get("mission_result"), "cur": st.get("current_task_id"), "ret": st.get("returning_task_id")}
        log["polls"].append(p)
        if p["phys"] != (log["polls"][-2]["phys"] if len(log["polls"]) > 1 else None):
            print(f"[{p['t']:6.1f}] {p['status']} {p['phys']} alt {p['alt_rel']:.1f} v {p['v']} armed {p['armed']} {p['mode']}", flush=True)
        if a.abort_after_s and aborted is None and p["t"] >= a.abort_after_s:
            ra = c.post(f"/uav/{RID}/task/{key}/abort", json={"reason": "PRETEST_ABORT"})
            aborted = {"t": p["t"], "code": ra.status_code, "body": ra.json()}
            log["abort"] = aborted
            print("abort", ra.status_code, flush=True)
        if a.link_cut_s and link_cut is None and p["t"] >= a.link_cut_s and p["armed"]:
            link("stop")
            link_cut = p["t"]
            log["link_cut"] = link_cut
            print("link cut", flush=True)

        done = tk.get("status") in ("COMPLETED", "FAILED", "CANCELLED") and p["phys"] in ("LANDED", "DONE", None) and not p["armed"]
        if done and p["t"] > 20:
            break
        time.sleep(1)
    time.sleep(5)
    trk.terminate()
    for k_, path in (("task_final", f"/uav/{RID}/task/{key}"), ("state_final", f"/uav/{RID}/state")):
        try:
            log[k_] = c.get(path).json()
        except Exception as e:  # noqa: BLE001
            log[k_] = {"error": str(e)[:200]}
    log["analysis"] = analyze(out_dir / "track.csv", log["polls"], home, tuple(a.target))
    log["end_local"] = time.strftime("%F %T")
    (out_dir / "run.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"task": {k: log["task_final"].get(k) for k in ("status", "mission_result", "physical_state", "error")},
                      "analysis": log["analysis"]}, ensure_ascii=False, indent=1))
    print("기록:", out_dir / "run.json")


if __name__ == "__main__":
    main()
