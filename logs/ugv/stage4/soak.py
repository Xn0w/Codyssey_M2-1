"""7단계 지속 운용: 4대 반복 출동·정차·복귀, 대기 뒤 재출발, 목표 교체·취소, 차량별 독립 장애(고장 주입 → 운영자 해제),
서버 재시작 뒤 상태 정리. RTF·명령 지연·텔레메트리 누락·서버 메모리·로그 크기를 주기적으로 기록한다.
  python logs/ugv/stage4/soak.py --minutes 120 --restart-at 60 --restart-cmd "bash logs/ugv/stage4/restart_server_wt.sh soak ugv/fleet_ab.json"
기록: logs/ugv/stage4/soak_<시각>.json (+ fleet_soak_*.csv 트랙)
"""
import argparse
import json
import pathlib
import random
import subprocess
import sys
import time

sys.path.insert(0, ".")
from ugv.tools import fleet_test  # noqa: E402
from ugv.geo import FRAME  # noqa: E402

OUT = pathlib.Path("logs/ugv/stage4")
RIDS = ("A-ugv1", "A-fire1", "B-ugv1", "B-fire1")


def server_mem():
    """8100 서버 프로세스 메모리 (MB, Windows tasklist)."""
    try:
        out = subprocess.run("netstat -ano -p TCP", capture_output=True, text=True, shell=True).stdout
        pid = next(l.split()[-1] for l in out.splitlines() if ":8100 " in l and "LISTENING" in l)
        t = subprocess.run(f'tasklist /FI "PID eq {pid}" /FO CSV /NH', capture_output=True, text=True, shell=True).stdout
        return pid, float(t.split('","')[-1].strip().strip('"').replace(",", "").replace(" K", "")) / 1024
    except Exception:  # noqa: BLE001
        return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=120)
    ap.add_argument("--restart-at", type=float, default=60, help="몇 분째 서버 재시작 (0 이면 안 함)")
    ap.add_argument("--restart-cmd", default="")
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    net, acc, ll = fleet_test.targets()
    # 목표 후보: 거점 주변 오프셋 (평가로 받아들여지는 것만 씀)
    cand = {"A": [ll("A", dx, dy) for dx, dy in ((-900, -700), (900, 600), (-1500, 300), (600, -1200), (1800, 1500), (-400, 1600))],
            "B": [(37.951004, 128.337462), (37.955735, 128.317915), (37.9600, 128.3300), (37.9450, 128.3250)]}
    run = fleet_test.Run("soak", a.minutes * 60 + 600)
    end = time.time() + a.minutes * 60
    st = {r: {"phase": "IDLE", "key": None, "n": 0, "wait_until": 0.0} for r in RIDS}
    log = run.log
    log.update({"soak": {"minutes": a.minutes, "seed": a.seed, "restart_at_min": a.restart_at}, "cycles": [], "metrics": [],
                "restart": None, "anomalies": []})
    restarted = False
    last_metric = 0.0
    k = 0
    import traceback
    aborted = None
    errs_in_row = 0
    try:
        while time.time() < end:
            try:
                p = run.poll()
            except Exception as e:  # noqa: BLE001  (재시작 중 등)
                log["anomalies"].append({"t": run.t(), "poll_error": str(e)[:200]})
                time.sleep(3)
                continue
            now = time.time()
            if now - last_metric > 60:
                pid, mem = server_mem()
                sizes = {f.name: f.stat().st_size for f in OUT.glob("state_soak*/*") if f.is_file()}
                log["metrics"].append({"t": run.t(), "server_pid": pid, "server_mem_mb": mem, "state_files_bytes": sizes,
                                       "tick_ms": p.get("tick_ms"),
                                       "tel_age_max": max((v["tel_age_s"] or 0) for v in p["vehicles"].values())})
                last_metric = now
            if a.restart_at and not restarted and run.t() > a.restart_at * 60 and a.restart_cmd:
                before = {r: run.c.get(f"/ugv/{r}/state").json() for r in RIDS}
                t_r = time.time()
                subprocess.run(a.restart_cmd, shell=True)
                after = {}
                for _ in range(120):
                    try:
                        after = {r: run.c.get(f"/ugv/{r}/state").json() for r in RIDS}
                        break
                    except Exception:  # noqa: BLE001
                        time.sleep(2)
                log["restart"] = {"t": run.t(), "took_s": round(time.time() - t_r, 1),
                                  "before": {r: {k_: v.get(k_) for k_ in ("state", "mission_state", "current_task_id", "speed_mps")}
                                             for r, v in before.items()},
                                  "after": {r: {k_: v.get(k_) for k_ in ("state", "mission_state", "current_task_id", "speed_mps", "fault")}
                                            for r, v in after.items()}}
                restarted = True
                print(f"[{run.t():7.1f}] 서버 재시작 {log['restart']['took_s']} s", flush=True)
                continue
            try:
                for rid in RIDS:
                    v = p["vehicles"][rid]
                    s = st[rid]
                    base = rid[0]
                    if s["phase"] in ("OUT", "HOME") and s["key"]:
                        t = run.task(rid, s["key"])
                        if t.get("status") in ("COMPLETED", "FAILED", "CANCELLED") and v["mission"] == "IDLE":
                            log["cycles"].append({"t": run.t(), "rid": rid, "key": s["key"], "phase": s["phase"], "status": t.get("status"),
                                                  "error": t.get("error"), "physical": t.get("physical_state")})
                            if s["phase"] == "OUT":
                                s["phase"], s["wait_until"] = "DWELL", now + rnd.uniform(10, 60)       # 도착 뒤 대기 → 복귀
                            else:
                                s["phase"], s["wait_until"] = "IDLE", now + rnd.uniform(20, 90)        # 거점 대기 → 재출발
                            s["key"] = None
                        elif s["phase"] == "OUT" and not s.get("twist") and rnd.random() < 0.004:
                            # 주행 중 목표 교체(50 %) 또는 취소(50 %)
                            s["twist"] = True
                            if rnd.random() < 0.5:
                                la, lo = rnd.choice(cand[base])
                                k += 1
                                key = f"SK{k}-{rid}"
                                rec = run.go(rid, key, la, lo)
                                log["cycles"].append({"t": run.t(), "rid": rid, "event": "RETARGET", "from": s["key"], "to": key,
                                                      "code": rec["status_code"]})
                                if rec["status_code"] == 200:
                                    s["key"] = key
                            else:
                                r = run.c.post(f"/ugv/{rid}/task/{s['key']}/abort", json={"reason": "SOAK_CANCEL"})
                                log["cycles"].append({"t": run.t(), "rid": rid, "event": "CANCEL", "key": s["key"], "code": r.status_code})
                    elif s["phase"] == "FAULT":
                        if v["speed"] is not None and v["speed"] < 0.1 and now > s["wait_until"]:
                            r = run.c.post(f"/ugv/{rid}/stop", json={"reason": "SOAK_OPERATOR_RELEASE"})
                            log["cycles"].append({"t": run.t(), "rid": rid, "event": "RELEASE", "code": r.status_code, "resp": r.json()})
                            if v["state"] != "UNAVAILABLE" or r.status_code == 200:
                                s["phase"], s["wait_until"] = "DWELL", now + 20
                    elif s["phase"] in ("IDLE", "DWELL") and now > s["wait_until"] and v["state"] == "READY":
                        k += 1
                        if s["phase"] == "DWELL":
                            key = f"SH{k}-{rid}"
                            rec = run.home(rid, key)
                            s["phase"] = "HOME"
                        else:
                            la, lo = rnd.choice(cand[base])
                            key = f"SK{k}-{rid}"
                            rec = run.go(rid, key, la, lo)
                            s["phase"] = "OUT"
                            s["twist"] = False
                        s["n"] += 1
                        if rec["status_code"] == 200:
                            s["key"] = key
                        else:
                            s["phase"], s["wait_until"] = ("DWELL" if s["phase"] == "HOME" else "IDLE"), now + 30
                    # 독립 장애: 주행 중 드물게 고장 주입 → 서고 나면 운영자 해제
                    if s["phase"] == "OUT" and (v["speed"] or 0) > 8 and rnd.random() < 0.0015 and not s.get("faulted_once"):
                        r = run.c.post(f"/ugv/{rid}/_test/fault", json={"code": "VEHICLE_FAULT", "detail": "지속 운용 시험 고장 주입"})
                        log["cycles"].append({"t": run.t(), "rid": rid, "event": "FAULT_INJECT", "code": r.status_code})
                        s.update(phase="FAULT", wait_until=now + 15, faulted_once=True, key=None)
            except Exception as e:  # noqa: BLE001 — 응답 하나가 이상해도(서버 500 등) 시험을 끝내지 않고 기록
                log["anomalies"].append({"t": run.t(), "cycle_error": f"{type(e).__name__}: {e}"[:300]})
                errs_in_row += 1
                if errs_in_row > 30:
                    raise
            else:
                errs_in_row = 0
            time.sleep(2)
    except Exception:  # noqa: BLE001 — 시험이 죽어도 원시 기록 경로·명령·실패 사유를 남긴다
        aborted = traceback.format_exc()[-2000:]
        print(aborted, flush=True)
    if aborted:
        print("기록:", run.finish(aborted=aborted))
        return
    # 마무리: 모두 복귀
    homes = []
    for rid in RIDS:
        k += 1
        key = f"SEND{k}-{rid}"
        if run.c.get(f"/ugv/{rid}/state").json()["state"] == "READY":
            rec = run.home(rid, key)
            if rec["status_code"] == 200:
                homes.append((rid, key))
    run.wait(homes, 900)
    out = run.finish()
    print("기록:", out if out else "")


if __name__ == "__main__":
    main()
