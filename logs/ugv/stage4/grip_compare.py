"""4번 지형 접지 원인 분리 판정 (chain16): 같은 차량·경로·속도, 평면 바닥 / 평탄 높이장 / 실제 지형 높이장.
회전 구간(|조향| > 0.15 rad, 속도 > 0.8 m/s)에서
  요율 비 = Gazebo 실제 요율 / 운동학 요율(v·tan(조향)/축거) — 1 이면 미끄럼 없음, 작을수록 앞바퀴가 덜 문다(언더스티어)
  미끄럼각 = 속도 방향과 차체 방향 차이
그리고 차체 이탈(road_test 분석, 원시 표본 기준 coverage_judge), 롤·피치 최대.
  python logs/ugv/stage4/grip_compare.py [--glob 'logs/ugv/c16_*.json']
"""
import argparse
import glob
import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, ".")
from ugv.profiles import get  # noqa: E402
from ugv.roads import RoadNetwork  # noqa: E402
from ugv.tools import coverage_judge as CJ  # noqa: E402
from ugv.tools.drive_test import load_track  # noqa: E402


def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * (len(xs) - 1)))], 3)


def metrics(rows, prof, net, g):
    ratios, slips = [], []
    for i in range(5, len(rows) - 5):
        a, b = rows[i - 5], rows[i + 5]
        dt = b["sim_t"] - a["sim_t"]
        if dt <= 0:
            continue
        v = math.hypot(b["x"] - a["x"], b["y"] - a["y"]) / dt
        st = rows[i]["steer_rad"]
        if abs(st) < 0.15 or v < 0.8:
            continue
        dyaw = (b["yaw"] - a["yaw"] + math.pi) % (2 * math.pi) - math.pi
        yr = dyaw / dt
        kin = v * math.tan(st) / prof.wheelbase_m
        if abs(kin) > 1e-3:
            ratios.append(yr / kin)
        hv = math.atan2(b["y"] - a["y"], b["x"] - a["x"])
        slips.append(abs(math.degrees((hv - rows[i]["yaw"] + math.pi) % (2 * math.pi) - math.pi)))
    exs = [CJ.body_excess(g, prof, r) for r in rows[::4]]
    return {"turn_samples": len(ratios), "yawrate_ratio_p10": pct(ratios, 0.1), "yawrate_ratio_p50": pct(ratios, 0.5),
            "slip_deg_p95": pct(slips, 0.95), "offroad_max_m": round(max(exs), 3) if exs else None,
            "offroad_samples": sum(1 for e in exs if e > 0),
            "max_roll_deg": round(max(abs(math.degrees(r["roll"])) for r in rows), 2),
            "max_pitch_deg": round(max(abs(math.degrees(r["pitch"])) for r in rows), 2),
            "z_range_m": round(max(r["z"] for r in rows) - min(r["z"] for r in rows), 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default="logs/ugv/c16_*.json")
    a = ap.parse_args()
    net = RoadNetwork()
    out = {}
    for f in sorted(glob.glob(a.glob)):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        csvp = Path(f.replace(".json", ".csv"))
        if not csvp.exists() or not d.get("rid"):
            continue
        prof = get("adair_ugv" if "ugv" in d["rid"] else "adair_firetruck")
        rows = load_track(csvp)
        m = metrics(rows, prof, net, net.graph_for(prof))
        rd = ((d.get("analysis") or {}).get("overall") or {}).get("road_dev") or {}
        m["road_test_offroad_max_m"] = rd.get("body_outside_est_road_max_m")
        m["world"] = d.get("world")
        m["tasks"] = {k: (t.get("status"), t.get("error")) for k, t in (d.get("tasks") or {}).items()} if isinstance(d.get("tasks"), dict) else None
        out[Path(f).stem] = m
        print(Path(f).stem, json.dumps(m, ensure_ascii=False))
    Path("logs/ugv/stage4/grip_compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
