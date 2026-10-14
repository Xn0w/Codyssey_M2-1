"""정지 감독 Gazebo 재검증 (2026-10-11 지속 운용 폭주 재현 조건). 차종별로: 고속 고장 주입·고속 취소·링크 단절 15 s·주행 중 서버 재시작.
판정 (Gazebo 실제 궤적): 명령 시점 속도, 정지(0.2 m/s 미만 2 s)까지 실제 이동 거리·시간, 정차 뒤 60 s 재이동(최대 변위),
정차 확인 전 READY 여부(같은 벽시계 Gazebo 속도), 서버 사건(STOP_CONFIRMED·STOP_NOT_CONFIRMED·STOP_CUT_DRIVE).
  bash logs/ugv/stage4/run_sc_wt.sh c14_stopv logs/ugv/stage4/pair_a_spawn.txt logs/ugv/stage4/pair_a_fleet.json \
       .venv/Scripts/python.exe logs/ugv/stage4/stop_verify.py --restart-cmd "bash logs/ugv/stage4/restart_server_wt.sh c14_stopv logs/ugv/stage4/pair_a_fleet.json"
"""
import argparse
import csv
import json
import math
import subprocess
import sys
import time

sys.path.insert(0, ".")
from ugv.tools import fleet_test  # noqa: E402

RIDS = ["A-ugv1", "A-fire1"]


def gz_rows(path, t_from):
    out = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            w = float(r.get("wall_t") or 0)
            if w >= t_from:
                out.append((w, float(r["sim_t"]), float(r["x"]), float(r["y"])))
    return out


def gz_speed(rows, i, half=5):
    j, k = max(0, i - half), min(len(rows) - 1, i + half)
    dt = rows[k][1] - rows[j][1]
    return math.dist(rows[k][2:4], rows[j][2:4]) / dt if dt > 0 else 0.0


def judge(path, t_cmd, t_end, polls):
    rows = [r for r in gz_rows(path, t_cmd - 1.0) if r[0] <= t_end]
    if len(rows) < 20:
        return {"error": "궤적 부족", "rows": len(rows)}
    i0 = next(i for i, r in enumerate(rows) if r[0] >= t_cmd)
    v_cmd = gz_speed(rows, i0)
    travel, stop_i, still_since = 0.0, None, None
    for i in range(i0 + 1, len(rows)):
        travel += math.dist(rows[i][2:4], rows[i - 1][2:4])
        if gz_speed(rows, i) < 0.2:
            still_since = still_since if still_since is not None else i
            if rows[i][1] - rows[still_since][1] >= 2.0:
                stop_i = still_since
                break
        else:
            still_since = None
    if stop_i is None:
        return {"v_cmd_mps": round(v_cmd, 2), "stopped": False, "travel_m": round(travel, 1)}
    d_stop = sum(math.dist(rows[i][2:4], rows[i - 1][2:4]) for i in range(i0 + 1, stop_i + 1))
    p_stop = rows[stop_i][2:4]
    after = [r for r in rows[stop_i:] if r[0] <= rows[stop_i][0] + 60.0]
    remove = max((math.dist(r[2:4], p_stop) for r in after), default=0.0)
    t_stop_wall = rows[stop_i][0]
    ready_early = [p for p in polls if p["wall"] < t_stop_wall and p["state"] == "READY"]
    return {"v_cmd_mps": round(v_cmd, 2), "stopped": True, "stop_dist_m": round(d_stop, 1),
            "stop_time_s": round(rows[stop_i][1] - rows[i0][1], 1), "remotion_60s_max_m": round(remove, 2),
            "watched_after_stop_s": round(after[-1][0] - after[0][0], 1) if after else 0.0,
            "ready_before_stop": len(ready_early)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--restart-cmd", default="")
    ap.add_argument("--scenarios", default="fault,abort,link,restart")
    a = ap.parse_args()
    run = fleet_test.Run("stopv", 4 * 3600, rids=RIDS)
    net, acc, ll = fleet_test.targets()
    tgt = {"A-ugv1": ll("A", -1500, 300), "A-fire1": ll("A", 1800, 1500)}
    res = []
    k = 0
    for sc in a.scenarios.split(","):
        for rid in RIDS:
            k += 1
            key = f"V{k}-{sc}-{rid}"
            rec = run.go(rid, key, *tgt[rid])
            if rec["status_code"] != 200:
                res.append({"scenario": sc, "rid": rid, "error": f"출동 거절 {rec['response']}"})
                continue
            # 고속까지 (소방차 최고 속도가 낮으면 그 85 %)
            t0 = time.time()
            vmax = 0.0
            while time.time() - t0 < 240:
                s = run.c.get(f"/ugv/{rid}/state").json()
                vmax = max(vmax, s["speed_mps"] or 0.0)
                if (s["speed_mps"] or 0) > (10.0 if "ugv" in rid else 8.0):
                    break
                time.sleep(0.5)
            polls = []
            t_cmd = time.time()
            if sc == "fault":
                r = run.c.post(f"/ugv/{rid}/_test/fault", json={"code": "VEHICLE_FAULT", "detail": "정지 재검증 고장 주입"})
            elif sc == "abort":
                r = run.c.post(f"/ugv/{rid}/task/{key}/abort", json={"reason": "STOP_VERIFY_ABORT"})
            elif sc == "link":
                r = run.c.post(f"/ugv/{rid}/_test/link", json={"cut": True})
            elif sc == "retarget":
                # 고속 주행 중 먼 목표로 교체 (긴 미션 업로드 — 2026-10-11 지속 운용 도로 이탈 재현 조건). 정지가 아니라 계속 주행:
                # 판정은 끝의 차체 이탈·시작 지점 맞춤(last_sent start_item)·120 s 안 되돌기 여부
                far = ll("A", 1800, -2500) if "ugv" in rid else ll("A", -1500, -2500)
                r = run.go(rid, f"{key}-NEW", *far)
                code = r.get("status_code")
                time.sleep(120)
                st_new = run.c.get(f"/ugv/{rid}/state").json()
                res.append({"scenario": sc, "rid": rid, "key": key, "cmd_code": code, "state_after_120s": st_new.get("mission_state"),
                            "fault": st_new.get("fault"), "speed": st_new.get("speed_mps")})
                print(json.dumps(res[-1], ensure_ascii=False), flush=True)
                run.c.post(f"/ugv/{rid}/task/{key}-NEW/abort", json={"reason": "STOP_VERIFY_END"})
                time.sleep(25)
                run.c.post(f"/ugv/{rid}/stop", json={"reason": "STOP_VERIFY_RELEASE"})
                hk = f"VH{k}-{rid}"
                if run.home(rid, hk)["status_code"] == 200:
                    run.wait([(rid, hk)], 1200, every=3.0)
                continue
            elif sc == "restart":
                r = subprocess.run(a.restart_cmd, shell=True) if a.restart_cmd else None
            code = getattr(r, "status_code", getattr(r, "returncode", None))
            link_restored = False
            t_end = t_cmd + 150.0
            while time.time() < t_end:
                if sc == "link" and not link_restored and time.time() - t_cmd > 15.0:
                    run.c.post(f"/ugv/{rid}/_test/link", json={"cut": False})
                    link_restored = True
                try:
                    s = run.c.get(f"/ugv/{rid}/state").json()
                    polls.append({"wall": time.time(), "state": s["state"], "mission": s["mission_state"],
                                  "speed": s["speed_mps"], "fault": s["fault"]})
                except Exception as e:  # noqa: BLE001
                    polls.append({"wall": time.time(), "error": str(e)[:120], "state": None})
                time.sleep(0.5)
            ev = []
            try:
                ev = [e for e in run.c.get(f"/ugv/{rid}/events?limit=200").json() if e.get("event", "").startswith(("STOP", "UNSUPERVISED", "FAULT"))]
            except Exception:  # noqa: BLE001
                pass
            j = judge(run.csv[rid], t_cmd, t_end, polls)
            out = {"scenario": sc, "rid": rid, "key": key, "cmd_code": code, "vmax_before": round(vmax, 2), **j,
                   "events": [{x: e.get(x) for x in ("event", "why", "basis", "travel_m", "allow_m", "time_s", "cut_drive", "ok", "v0_mps", "speed_mps")}
                              for e in ev][-12:],
                   "final": polls[-1] if polls else None}
            res.append(out)
            print(json.dumps({x: out.get(x) for x in ("scenario", "rid", "v_cmd_mps", "stopped", "stop_dist_m", "stop_time_s",
                                                       "remotion_60s_max_m", "ready_before_stop")}, ensure_ascii=False), flush=True)
            run.log["stop_verify"] = res
            run.checkpoint()
            # 해제·복귀 (다음 시나리오 준비)
            run.c.post(f"/ugv/{rid}/stop", json={"reason": "STOP_VERIFY_RELEASE"})
            time.sleep(3)
            run.c.post(f"/ugv/{rid}/stop", json={"reason": "STOP_VERIFY_RELEASE"})
            hk = f"VH{k}-{rid}"
            if run.home(rid, hk)["status_code"] == 200:
                run.wait([(rid, hk)], 900, every=3.0)
    run.log["stop_verify"] = res
    print("기록:", run.finish())


if __name__ == "__main__":
    main()
