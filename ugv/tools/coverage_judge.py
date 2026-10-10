# -*- coding: utf-8 -*-
"""ugv/tools/coverage_judge.py — 실제 주행 커버리지 판정 (원시 Gazebo 궤적 CSV 에서 직접).

저장된 분석 요약에 기대지 않는다 (2026-10-11 검토: 분석이 없으면 기본값으로 이탈 0 처리, 다중 차량 분석은 이탈 사건을 처음 10개만 저장,
최소·최대 s 차이로 주행 범위를 재서 중간 누락을 못 봄, 짧은 도로에서 '길이 × 90 % − 6 m' 가 음수라 정지 표본 하나로 통과).
- 차체 이탈: 0.2 s 마다 차체 둘레 표본 vs 차량별 추정 도로 띠 (fleet_test.analyze·road_test 와 같은 기준). 모든 이탈 표본을 도로에 붙인다.
- 전복: |roll| 또는 |pitch| > 45°.
- 통과 구간: 연속된 유효 표본 쌍(시각 간격 ≤ GAP_MAX_S, 같은 도로, s 차이 ≤ STEP_MAX_M)이 덮은 칸(BIN_M, 짧은 도로는 최소 MIN_BINS 칸)만.
  덮은 칸 비율 ≥ COVER_MIN 이어야 '지나감'. 정지 표본 하나, 중간 기록 누락은 덮지 않는다.
판정: 링크·차량별 관측 목록 → DRIVEN_FAIL (어느 관측에서든 이탈·전복) / DRIVEN_PASS (완결 기록 관측이 하나 이상, 모두 정상) /
  INCOMPLETE (지나간 관측이 불완전 기록뿐 — JSON 없음·분석 오류 등) / 관측 없음.
"""

import math

GAP_MAX_S = 1.0
STEP_MAX_M = 12.0
BIN_M = 2.0
MIN_BINS = 4
COVER_MIN = 0.9
SNAP_M = 3.0
SAMPLE_S = 0.2
ROLLOVER_RAD = math.radians(45)


def body_excess(g, prof, r):
    c, s = math.cos(r["yaw"]), math.sin(r["yaw"])
    off = prof.rear_axle_from_center_m
    return max(g.outside_m(r["x"] + (fx - off) * c - fy * s, r["y"] + (fx - off) * s + fy * c) for fx, fy in prof.body_samples)


def scan(net, g, prof, rows):
    """궤적 → (링크별 덮은 칸 {rid: set(bin)}, 이탈 표본 [(x, y, excess, rid)], 전복 표본 [(x, y, rid)], 표본 수, 최대 시각 간격)."""
    covered, bad, roll = {}, [], []
    prev, last_t, gap_max, n = None, -1e9, 0.0, 0
    for r in rows:
        if r["sim_t"] - last_t < SAMPLE_S - 1e-6:
            continue
        if last_t > -1e8:
            gap_max = max(gap_max, r["sim_t"] - last_t)
        last_t = r["sim_t"]
        n += 1
        p = net.snap(r["x"], r["y"], max_m=SNAP_M)
        ex = body_excess(g, prof, r)
        if ex > 0 or abs(r["roll"]) > ROLLOVER_RAD or abs(r["pitch"]) > ROLLOVER_RAD:
            q = p or net.snap(r["x"], r["y"], max_m=20.0)
            rid = q.road_id if q is not None else None
            if ex > 0:
                bad.append((r["x"], r["y"], ex, rid))
            if abs(r["roll"]) > ROLLOVER_RAD or abs(r["pitch"]) > ROLLOVER_RAD:
                roll.append((r["x"], r["y"], rid))
        cur = (r["sim_t"], p) if p is not None else None
        if cur and prev and prev[1].road_id == p.road_id and cur[0] - prev[0] <= GAP_MAX_S \
                and abs(p.s - prev[1].s) <= STEP_MAX_M:
            L = net.roads[p.road_id].length
            nb = max(MIN_BINS, int(math.ceil(L / BIN_M)))
            w = L / nb
            lo, hi = sorted((prev[1].s, p.s))
            if hi > lo:
                b0, b1 = int(lo / w), min(nb - 1, int(hi / w))
                # 칸을 덮었다 = 그 칸 안 구간 길이가 칸 폭의 절반 이상이거나 양 끝 사이 안쪽 칸
                cs = covered.setdefault(p.road_id, {})
                for b in range(b0, b1 + 1):
                    seg = min(hi, (b + 1) * w) - max(lo, b * w)
                    cs[b] = cs.get(b, 0.0) + max(seg, 0.0)
        prev = cur
    full = {}
    for rid, cs in covered.items():
        L = net.roads[rid].length
        nb = max(MIN_BINS, int(math.ceil(L / BIN_M)))
        w = L / nb
        full[rid] = sum(1 for b in range(nb) if cs.get(b, 0.0) >= 0.5 * w) / nb
    return full, bad, roll, n, gap_max


def observations(net, g, prof, rows, complete: bool, run: str):
    """한 궤적의 링크별 관측 {rid: {...}} — 지나간 링크(덮은 비율 ≥ COVER_MIN)와 이탈·전복이 난 링크."""
    full, bad, roll, n, gap_max = scan(net, g, prof, rows)
    out = {}
    for rid, frac in full.items():
        if frac >= COVER_MIN:
            out[rid] = {"run": run, "cover": round(frac, 3), "complete": complete, "offroad_max_m": 0.0,
                        "offroad_samples": 0, "rollover": False}
    for x, y, ex, rid in bad:
        if rid is None:
            continue
        o = out.setdefault(rid, {"run": run, "cover": round(full.get(rid, 0.0), 3), "complete": complete,
                                 "offroad_max_m": 0.0, "offroad_samples": 0, "rollover": False})
        o["offroad_max_m"] = round(max(o["offroad_max_m"], ex), 3)
        o["offroad_samples"] += 1
    for x, y, rid in roll:
        if rid is not None:
            out.setdefault(rid, {"run": run, "cover": round(full.get(rid, 0.0), 3), "complete": complete,
                                 "offroad_max_m": 0.0, "offroad_samples": 0, "rollover": False})["rollover"] = True
    meta = {"samples": n, "pose_gap_max_s": round(gap_max, 3), "offroad_samples": len(bad),
            "offroad_max_m": round(max((b[2] for b in bad), default=0.0), 3), "rollover_samples": len(roll)}
    return out, meta


def judge(obs_list):
    """링크 하나의 관측 목록 → (상태, 설명)."""
    if not obs_list:
        return None, ""
    fails = [o for o in obs_list if o["offroad_samples"] > 0 or o["rollover"]]
    if fails:
        w = max(o["offroad_max_m"] for o in fails)
        return "DRIVEN_FAIL", f"{len(fails)}/{len(obs_list)} 관측 이탈·전복 (최대 {w:.2f} m)"
    passed = [o for o in obs_list if o["cover"] >= COVER_MIN and o["complete"]]
    if passed:
        return "DRIVEN_PASS", f"{len(passed)} 회 (완결 기록)"
    return "INCOMPLETE", f"{len(obs_list)} 관측, 완결 기록 없음 (JSON·분석 없음 또는 통과 덮음 부족)"
