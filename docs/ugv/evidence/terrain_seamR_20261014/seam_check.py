"""R0/R1 정지 재현 분석 (WSL python3, 사전 기준 SEAMR_criteria.md). 사용: python3 seam_check.py <tiles_v2> <out_dir> <TAG> <R0|R1> [기대 타일]
정착 = 기록 첫 sim_t + 2.0 s 이후. 바퀴 링크 z − 분석 지면 (링크 xy, 쌍선형 — 엔진 격자 1024/1025 압축으로 경계 근처 최대 ≈ 2.5 cm 차이 가능, 기록).
R0 PASS: 기록기 rc 0·무효/중단 표식 없음, 서스펜션 관절 발행, 네 바퀴 접촉 VALID ≥ 95 % (정착 뒤), 접촉 상대 이름에 기대 타일 포함,
|롤|·|피치| ≤ 2°, 서스펜션 |q| < 0.098, 바퀴 링크 z − 지면 ∈ [0.29, 0.41] (반지름 0.35 ± 0.06). R1 = 판정 없이 기록 (보고 뒤 다음 게이트)."""
import csv, json, math, sys
import numpy as np
from PIL import Image
from pathlib import Path
T = Path(sys.argv[1]); O = Path(sys.argv[2]); tag = sys.argv[3]; kind = sys.argv[4]; want_tile = sys.argv[5] if len(sys.argv) > 5 else None
meta = json.load(open(T / "tiles.json")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]; ALT = meta["world_origin_alt_m"]; _img = {}
def z_at(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); name = f"T{i:02d}_{j:02d}"; t = meta["tiles"][name]
    if name not in _img: _img[name] = np.asarray(Image.open(T / name / "heightmap.png"), dtype=np.float64)
    img = _img[name]; x0, y0, x1, y1 = t["bounds"]; n = img.shape[0] - 1
    fc, fr = (x - x0) / (x1 - x0) * n, (y1 - y) / (y1 - y0) * n; c0, r0 = min(int(fc), n - 1), min(int(fr), n - 1); dc, dr = fc - c0, fr - r0
    v = img[r0, c0] * (1 - dc) * (1 - dr) + img[r0, c0 + 1] * dc * (1 - dr) + img[r0 + 1, c0] * (1 - dc) * dr + img[r0 + 1, c0 + 1] * dc * dr
    return name, t["zmin"] + v / 65535.0 * t["span"] - ALT
W = ["wheel_front_left", "wheel_front_right", "wheel_rear_left", "wheel_rear_right"]; SUSP = ["susp_front_left", "susp_front_right", "susp_rear_left", "susp_rear_right"]
rec = {"tag": tag, "kind": kind, "markers": [m for m in ("contaminated", "invalid", "invalid_evidence", "invalid_stop", "abort") if (O / f"{tag}.{m}").exists()]}
try:
    gl = (O / f"{tag}_gz_detail.log").read_text().strip().splitlines(); rec["gz_detail_rc"] = int(gl[-1].split("=")[1])
except Exception as e:  # noqa: BLE001
    rec["gz_detail_rc"] = None; rec["log_error"] = repr(e)
m = json.load(open(O / f"{tag}_meta.json")); rec["meta"] = {k: m.get(k) for k in ("rows", "dt_median_s", "dt_max_s", "susp_joints_published", "contact_other_counts", "abort", "completed")}
rows = list(csv.DictReader(open(O / f"{tag}.csv")))
t0 = float(rows[0]["sim_t"]); S = [r for r in rows if float(r["sim_t"]) >= t0 + 2.0]
rec["n_rows"], rec["n_settled"] = len(rows), len(S)
def f(r, k):
    try: return float(r[k])
    except (ValueError, KeyError): return None
wh = {}
for w in W:
    st = [r[f"{w}_c_state"] for r in S]; dz = []
    for r in S:
        lx, ly, lz = f(r, f"{w}_link_x"), f(r, f"{w}_link_y"), f(r, f"{w}_z")
        if None not in (lx, ly, lz): dz.append(lz - z_at(lx, ly)[1])
    dep = [f(r, f"{w}_depth") for r in S if f(r, f"{w}_depth") is not None]; fz = [f(r, f"{w}_fz") for r in S if f(r, f"{w}_fz") is not None]
    oth = sorted({r[f"{w}_other"] for r in S if r[f"{w}_other"]})
    last = S[-1] if S else {}
    wh[w] = {"valid_ratio": round(st.count("VALID") / max(1, len(st)), 4), "states": {s_: st.count(s_) for s_ in set(st)}, "other": oth,
             "link_z_minus_ground": [round(min(dz), 4), round(max(dz), 4)] if dz else None, "depth_max": round(max(dep), 5) if dep else None,
             "fz_median": round(float(np.median(fz)), 1) if fz else None, "tile_at_link_last": z_at(f(last, f"{w}_link_x"), f(last, f"{w}_link_y"))[0] if last and f(last, f"{w}_link_x") is not None else None}
rec["wheels"] = wh
rp = [(abs(math.degrees(f(r, "roll"))), abs(math.degrees(f(r, "pitch")))) for r in S]
rec["roll_abs_max_deg"] = round(max(a for a, _ in rp), 3) if rp else None; rec["pitch_abs_max_deg"] = round(max(b for _, b in rp), 3) if rp else None
q = {s_: [f(r, f"{s_}_q") for r in S if f(r, f"{s_}_q") is not None] for s_ in SUSP}
rec["susp_q_range"] = {s_: [round(min(v), 5), round(max(v), 5)] if v else None for s_, v in q.items()}
bz = [f(r, "z") - z_at(f(r, "x"), f(r, "y"))[1] for r in S]; rec["base_dz_range"] = [round(min(bz), 4), round(max(bz), 4)] if bz else None
rec["sum_fz_median"] = round(sum(w_["fz_median"] or 0 for w_ in wh.values()), 1)
if kind == "R0":
    c = {"recorder_ok_no_markers": rec["gz_detail_rc"] == 0 and not rec["markers"],
         "susp_published": bool(rec["meta"]["susp_joints_published"]),
         "contact_valid_95": all(w_["valid_ratio"] >= 0.95 for w_ in wh.values()),
         "contact_expected_tile": None if not want_tile else all(any(want_tile in o for o in w_["other"]) for w_ in wh.values()),
         "attitude_le_2deg": rp != [] and rec["roll_abs_max_deg"] <= 2.0 and rec["pitch_abs_max_deg"] <= 2.0,
         "susp_within_limit": all(v and max(abs(v[0]), abs(v[1])) < 0.098 for v in rec["susp_q_range"].values()),
         "wheel_height_0.29_0.41": all(w_["link_z_minus_ground"] and 0.29 <= w_["link_z_minus_ground"][0] and w_["link_z_minus_ground"][1] <= 0.41 for w_ in wh.values())}
    rec["checks"] = c
    rec["status"] = "FAIL" if any(v is False for v in c.values()) else ("UNCONFIRMED" if any(v is None for v in c.values()) else "PASS")
    if not any("T0" in o for w_ in wh.values() for o in w_["other"]): rec["note"] = "접촉 상대에 타일 이름 없음 — 높이장 접촉 토픽 미확인이면 계측 HOLD"
else:
    rec["status"] = "RECORDED"
json.dump(rec, open(O / f"check_{tag}.json", "w"), ensure_ascii=False, indent=1)
print(tag, rec["status"], json.dumps({k: rec.get(k) for k in ("checks", "markers", "roll_abs_max_deg", "pitch_abs_max_deg", "base_dz_range", "sum_fz_median")}, ensure_ascii=False))
for w, v in wh.items(): print(" ", w, v)
