# -*- coding: utf-8 -*-
"""원호별 실측 횡가속·추종 반경 (시험 도구). 사용: python latacc_v2.py <판정 v2 json> <실행 폴더>
정의 (계측 정의를 결과에 함께 남긴다):
  - 기준점: Gazebo 모델 자세 원점 (adair_ugv 모델 원점 — 차체 기준점, IMU 아님 → 중력 투영 없음, 지면 경사 무관)
  - 속도 v: 위치 차분 ±0.25 s (판정기와 같음), 회전율 ω: yaw 차분 ±0.25 s
  - a_lat = v·|ω|; 추종 반경 = v/|ω|
  - 원호 구간 = 판정기 v2 원호 s0~s1 (계획선 투영). 보고: 최대 a_lat, 원호 중앙 ±2 m 중앙값 a_lat·추종 반경, 평균 a_lat, v²/R_계획 최대
"""
import csv
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[4]))
import judge_corner_v2 as J  # noqa: E402
from ugv.geo import FRAME, GZ_FRAME  # noqa: E402


def main():
    jv = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    run = Path(sys.argv[2])
    plan = json.loads((HERE.parent / jv["plan"]).read_text(encoding="utf-8")) if (HERE.parent / jv["plan"]).exists() \
        else json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
    pxy = [tuple(p) for p in plan["plan_xy"]]
    pc = J.cumlen(pxy)
    f = sorted(run.glob("corner_*.csv"), key=lambda p: p.stat().st_mtime)[-1]
    rows = []
    for r in csv.DictReader(open(f, newline="")):
        try:
            t, gx, gy, yaw = float(r["sim_t"]), float(r["x"]), float(r["y"]), float(r["yaw"])
        except ValueError:
            continue
        x, y = FRAME.to_xy(*GZ_FRAME.to_ll(gx, gy))
        rows.append({"sim_t": t, "x": x, "y": y, "yaw": yaw})
    vs = J.track_speeds(rows)
    T = [r["sim_t"] for r in rows]
    w = []
    for i in range(len(rows)):
        j = i
        while j > 0 and T[i] - T[j] < 0.25:
            j -= 1
        k = i
        while k < len(rows) - 1 and T[k] - T[i] < 0.25:
            k += 1
        dt = T[k] - T[j]
        dy = (rows[k]["yaw"] - rows[j]["yaw"] + math.pi) % (2 * math.pi) - math.pi
        w.append(dy / dt if dt > 0 else 0.0)
    S, s_lo = [], 0.0
    import bisect
    for r in rows:
        k0 = max(0, bisect.bisect_left(pc, s_lo - 10.0) - 1)
        k1 = bisect.bisect_right(pc, s_lo + 100.0) + 1
        d, s = J.project_seg(pxy, pc, r["x"], r["y"], k0, k1)
        S.append(s)
        s_lo = max(s_lo, s)
    out = []
    for c in jv["corners"] + jv["extra_arcs"]:
        a = c.get("v2")
        if not a:
            continue
        s0, s1 = a["s_m"]
        R = a["R_m"]
        idx = [i for i in range(len(rows)) if s0 <= S[i] <= s1]
        if not idx:
            continue
        al = [vs[i] * abs(w[i]) for i in idx]
        mid = [i for i in idx if abs(S[i] - (s0 + s1) / 2) <= 2.0]
        rad = sorted(vs[i] / abs(w[i]) for i in mid if abs(w[i]) > 1e-3)
        out.append({"arc": c.get("corner") or c["arc"].get("i0"), "R_plan_m": R, "a_lat_max": round(max(al), 3),
                    "a_lat_mean": round(sum(al) / len(al), 3),
                    "a_lat_mid_median": round(sorted(vs[i] * abs(w[i]) for i in mid)[len(mid) // 2], 3) if mid else None,
                    "track_radius_mid_median_m": round(rad[len(rad) // 2], 2) if rad else None,
                    "v2_over_R_plan_max": round(max(vs[i] ** 2 / R for i in idx), 3)})
    print(json.dumps({"run": run.name, "arcs": out}, ensure_ascii=False))


if __name__ == "__main__":
    main()
