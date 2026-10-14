"""단계 B 추가 판정 (사전, Codex 0814 2절 B): 임시 선별 프로필 20 km/h 실제 적용·접지·이음매 통과. ADAIR 루트에서: python envB_extra.py <tag>
- speed_limit: 서버 health.env UGV_MAX_SPEED_KMH "20", 준비 /ugv profile max_speed_kmh 20, 첫 미션 항목 속도 ≤ 5.56, Gazebo 실제 최고 속도 ≤ 6.1 m/s (5.56 × 1.1).
- ground: gz 기록 pose 모델 원점 z − 지면 ∈ [−0.10, +0.10] m 전 구간, 정지 구간 |z − 지면| ≤ 0.03.
- seam: 기록 pose 가 T05_16 과 T04_16 둘 다 지남."""
import glob, json, math, sys
from pathlib import Path
R = Path(__file__).resolve().parents[5]; tag = sys.argv[1]; O = Path(__file__).resolve().parent; HK = R.parent / "ADAIR_wt_hook"
c, rec = {}, {"tag": tag}
js = sorted(glob.glob(str(HK / f"logs/ugv/{tag}_*.json")))
d = json.load(open(js[-1], encoding="utf-8")) if js else {}
env = ((d.get("health") or {}).get("env")) or {}
try:
    rd = json.load(open(R / f"logs/ugv/stage4/ready_{tag}.json", encoding="utf-8"))[0]; pk = rd["profile"]["max_speed_kmh"]
except Exception:  # noqa: BLE001
    pk = None
items = []
for e in d.get("events") or []:
    if e.get("event") in ("MISSION_UPLOAD", "FOLLOW", "MISSION_SENT") and e.get("items"):
        items = e["items"]; break
rows = []
if js:
    for ln in open(js[-1][:-5] + ".csv", encoding="utf-8").read().splitlines()[1:]:
        p = ln.split(","); rows.append((float(p[0]), float(p[1]), float(p[2])))
vmax = None
if len(rows) > 10:
    sp = []
    for i in range(len(rows)):
        j = next((k for k in range(i, len(rows)) if rows[k][0] - rows[i][0] >= 0.2), None)
        if j is None: break
        sp.append(math.dist(rows[i][1:], rows[j][1:]) / (rows[j][0] - rows[i][0]))
    vmax = round(max(sp), 3)
rec["speed"] = {"env_UGV_MAX_SPEED_KMH": env.get("UGV_MAX_SPEED_KMH"), "ready_profile_max_speed_kmh": pk, "gz_speed_max_mps": vmax,
                "first_items_speed_max": max((it.get("speed_mps") or it.get("v") or 0) for it in items) if items else None}
c["speed_limit_applied"] = None if (vmax is None or pk is None) else (env.get("UGV_MAX_SPEED_KMH") == "20" and abs(pk - 20.0) < 0.05 and vmax <= 6.1)
try:
    g = json.load(open(O / f"ground_{tag}.json", encoding="utf-8")); s = g["series"]
    rest = [x for x in s if x["v"] is not None and x["v"] < 0.05 and x["t"] >= s[0]["t"] + 5.0]
    rec["ground"] = {k: g[k] for k in ("n", "dz_min", "dz_max", "roll_abs_max", "pitch_abs_max", "tiles_seen")}
    c["ground_contact"] = all(-0.10 <= x["dz"] <= 0.10 for x in s if x["t"] >= s[0]["t"] + 5.0) and bool(rest) and all(abs(x["dz"]) <= 0.03 for x in rest)
    c["seam_crossed"] = {"T05_16", "T04_16"} <= set(g["tiles_seen"])
except Exception as e:  # noqa: BLE001
    rec["ground_error"] = repr(e); c["ground_contact"] = c["seam_crossed"] = None
rec["checks"] = c = {k: (None if v is None else bool(v)) for k, v in c.items()}   # (envB_c1 사본: bool 정규화 — Codex 0940 1절)
rec["status"] = "FAIL" if any(v is False for v in c.values()) else ("UNCONFIRMED" if any(v is None for v in c.values()) else "PASS")
json.dump(rec, open(O / f"envB_extra_{tag}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(tag, rec["status"], c, json.dumps(rec.get("speed"), ensure_ascii=False))
