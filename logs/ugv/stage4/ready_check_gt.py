"""정지 전 READY 전수 점검 — Gazebo 실제 속도(트랙 CSV, 0.5 s 창) 기준. 텔레메트리(PX4 EKF) 속도는 정지 직후 0.2~0.35 m/s 로 늦게
따라와 거짓 위반이 나온다 (2026-10-11 fleet_follow 2회차: Gazebo 정지 0.000 m/s 인데 텔레메트리 0.35).
  python logs/ugv/stage4/ready_check_gt.py "logs/ugv/fleet_*_2026101[01]_*.json"
"""
import bisect, glob, json, math, pathlib, sys
sys.path.insert(0, ".")
from ugv.tools.drive_test import load_track
bad, n, tel_only = [], 0, 0
for f in sorted(glob.glob(sys.argv[1])):
    d = json.load(open(f, encoding="utf-8"))
    t0 = d.get("start_wall")
    tracks = {}
    for rid, p in (d.get("csv") or {}).items():
        if pathlib.Path(p).exists():
            rows = [r for r in load_track(pathlib.Path(p)) if r.get("wall_t")]
            tracks[rid] = (rows, [r["wall_t"] for r in rows])
    for p in d.get("polls", []):
        for rid, v in p["vehicles"].items():
            if v["state"] != "READY" or rid not in tracks:
                continue
            n += 1
            rows, wt = tracks[rid]
            w = t0 + p["t"]
            i = bisect.bisect_left(wt, w)
            a, b = max(0, i - 3), min(len(rows) - 1, i + 3)
            if b <= a:
                continue
            gv = math.hypot(rows[b]["x"] - rows[a]["x"], rows[b]["y"] - rows[a]["y"]) / max(rows[b]["sim_t"] - rows[a]["sim_t"], 1e-3)
            if gv > 0.3:
                bad.append((pathlib.Path(f).name, p["t"], rid, round(gv, 2), v["speed"]))
            elif (v["speed"] or 0) > 0.3:
                tel_only += 1
print("READY 표본", n, "Gazebo 실제 속도 > 0.3 m/s 위반", len(bad), "(텔레메트리만 > 0.3:", tel_only, ")")
for b in bad[:20]:
    print(b)
