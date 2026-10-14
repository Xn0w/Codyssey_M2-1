"""(v2, A 재실행) + 기록 범위·준비 게이트·감시 기록 확인. A 단계 (원 B 조건 + 후보 c1) 고율 바퀴/접촉/서스펜션 판정 (WSL python3, 사전 기준 ENVB_C1_criteria.md). 사용: python3 detail_check.py <tiles_v2> <dir> <TAG>
기록 = gz_detail_seam.py (파티션 adair_ugv, 시험 동안). 판정 구간 = 기록 시작 + 5 s ~ 끝. 상태 규칙: 체크 값을 bool 로 정규화 뒤 False → FAIL, None → UNCONFIRMED."""
import csv, json, math, sys
import numpy as np
from PIL import Image
from pathlib import Path
T = Path(sys.argv[1]); O = Path(sys.argv[2]); tag = sys.argv[3]
meta = json.load(open(T / "tiles.json")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]; ALT = meta["world_origin_alt_m"]; _img = {}
def z_at(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); name = f"T{i:02d}_{j:02d}"; t = meta["tiles"][name]
    if name not in _img: _img[name] = np.asarray(Image.open(T / name / "heightmap.png"), dtype=np.float64)
    img = _img[name]; x0, y0, x1, y1 = t["bounds"]; n = img.shape[0] - 1
    fc, fr = (x - x0) / (x1 - x0) * n, (y1 - y) / (y1 - y0) * n; c0, r0 = min(int(fc), n - 1), min(int(fr), n - 1); dc, dr = fc - c0, fr - r0
    v = img[r0, c0] * (1 - dc) * (1 - dr) + img[r0, c0 + 1] * dc * (1 - dr) + img[r0 + 1, c0] * (1 - dc) * dr + img[r0 + 1, c0 + 1] * dc * dr
    return name, t["zmin"] + v / 65535.0 * t["span"] - ALT
W = ["wheel_front_left", "wheel_front_right", "wheel_rear_left", "wheel_rear_right"]; SUSP = ["susp_front_left", "susp_front_right", "susp_rear_left", "susp_rear_right"]
def f(r, k):
    try: return float(r[k])
    except (ValueError, KeyError, TypeError): return None
rec = {"tag": tag}; c = {}
try:
    m = json.load(open(O / f"detail_{tag}_meta.json")); rec["meta"] = {k: m.get(k) for k in ("rows", "dt_median_s", "dt_max_s", "susp_joints_published", "abort", "completed", "contact_other_counts")}
except Exception as e:  # noqa: BLE001
    m = None; rec["meta_error"] = repr(e)
R = list(csv.DictReader(open(O / f"detail_{tag}.csv"))) if (O / f"detail_{tag}.csv").exists() else []
c["recorder_rows_no_abort"] = None if m is None else (len(R) > 100 and not (m.get("abort") or {}).get("reason") and bool(m.get("susp_joints_published")))
if R:
    t0 = float(R[0]["sim_t"]); S = [r for r in R if float(r["sim_t"]) >= t0 + 5.0]
    rec["valid_ratio"] = {w: round([r[f"{w}_c_state"] for r in S].count("VALID") / max(1, len(S)), 4) for w in W}
    c["contact_valid_95"] = all(v >= 0.95 for v in rec["valid_ratio"].values())
    hz = {}
    for w in W:
        v = [f(r, f"{w}_z") - z_at(f(r, f"{w}_link_x"), f(r, f"{w}_link_y"))[1] for r in S if None not in (f(r, f"{w}_z"), f(r, f"{w}_link_x"), f(r, f"{w}_link_y"))]
        hz[w] = [round(float(min(v)), 4), round(float(max(v)), 4)] if v else None
    rec["wheel_height"] = hz; c["wheel_height_0.29_0.41"] = all(v and 0.29 <= v[0] and v[1] <= 0.41 for v in hz.values())
    q = {s_: [f(r, f"{s_}_q") for r in S if f(r, f"{s_}_q") is not None] for s_ in SUSP}
    rec["susp_q_range"] = {s_: [round(min(v), 5), round(max(v), 5)] if v else None for s_, v in q.items()}
    c["susp_within_limit"] = all(v and max(abs(v[0]), abs(v[1])) < 0.098 for v in rec["susp_q_range"].values())
    seq = {}
    for w in W:
        o = [r[f"{w}_other"] for r in S if r[f"{w}_other"]]; seq[w] = [x for i, x in enumerate(o) if i == 0 or x != o[i - 1]][:6]
    rec["contact_other_seq"] = seq
    c["all_wheels_T04_T05_T0517"] = all(all(any(t_ in x for x in s_) for t_ in ("T04_16", "T05_16", "T05_17")) for s_ in seq.values())   # (중거리) 세 타일 모두 접촉
    rp = [(abs(math.degrees(f(r, "roll"))), abs(math.degrees(f(r, "pitch")))) for r in S]
    rec["roll_pitch_abs_max_deg"] = [round(max(a for a, _ in rp), 3), round(max(b for _, b in rp), 3)]
else:
    c["contact_valid_95"] = c["wheel_height_0.29_0.41"] = c["susp_within_limit"] = c["all_wheels_T04_T05_T0517"] = None
# (v2, Codex 1000) 기록 범위: 고율 자료가 정지 확인 + 25 s (30 s 유지 관측 구간) 까지 이어지는가, 준비 게이트 통과 기록
try:
    sr = {r_["tag"]: r_ for r_ in json.load(open(O / "ts2_slope_report.json", encoding="utf-8"))}
    cst = ((sr.get(tag) or {}).get("hold") or {}).get("confirm_sim_t")
    rec["coverage"] = {"detail_last_sim": float(R[-1]["sim_t"]) if R else None, "hold_confirm_sim_t": cst}
    c["coverage_to_hold"] = None if (cst is None or not R) else float(R[-1]["sim_t"]) >= cst + 25.0
except Exception as e:  # noqa: BLE001
    rec["coverage_error"] = repr(e); c["coverage_to_hold"] = None
try:
    rd = json.load(open(O / f"detail_ready_{tag}.json")); rec["ready"] = rd; c["ready_gate"] = rd.get("ready") == 1
except Exception as e:  # noqa: BLE001
    rec["ready_error"] = repr(e); c["ready_gate"] = None
c["no_watchdog"] = not (O / f"detail_watchdog_{tag}.json").exists()
rec["checks"] = c = {k: (None if v is None else bool(v)) for k, v in c.items()}
rec["status"] = "FAIL" if any(v is False for v in c.values()) else ("UNCONFIRMED" if any(v is None for v in c.values()) else "PASS")
json.dump(rec, open(O / f"detail_check_{tag}.json", "w"), ensure_ascii=False, indent=1)
print(tag, rec["status"], json.dumps({k: rec.get(k) for k in ("checks", "valid_ratio", "roll_pitch_abs_max_deg", "wheel_height")}, ensure_ascii=False))
