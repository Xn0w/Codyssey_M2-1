"""단계 A 판정 (Codex 0814 2절 A — 주행 합격 아님): 월드 로드·정지 접지·텔레메트리·자원·사후 종료. ADAIR 루트에서: python envA_check.py <tag>
사전 기준 (ENVA_criteria.md): 래퍼 rc 0·표식 없음, 준비 위치 ↔ 스폰 ≤ 2 m, 폴링 READY·sim 시각 증가·갱신 나이 ≤ 2 s, 접지 |z−지면| ≤ 0.03 m·|롤|,|피치| ≤ 2°,
잔존 0. 메모리·RTF 는 특성 기록 (RTF 중앙값 < 0.5 면 보고 표시)."""
import csv, json, math, statistics, sys
from pathlib import Path
R = Path(__file__).resolve().parents[5]; tag = sys.argv[1]; O = Path(__file__).resolve().parent; S4 = R / "logs/ugv/stage4"
c, rec = {}, {"tag": tag}
try:
    w = json.load(open(S4 / f"rc_{tag}.json", encoding="utf-8")); rec["rc"] = w
    c["wrapper_rc0"] = w.get("test_rc") == 0 and w.get("copy_logs_rc") == 0 and str(w.get("stop_post_rc")) == "0" and w.get("invalid_stop") is False
except Exception as e:  # noqa: BLE001
    rec["rc_error"] = repr(e); c["wrapper_rc0"] = None
c["no_markers"] = not any((S4 / f"{tag}.{m}").exists() for m in ("contaminated", "invalid_evidence", "invalid_stop"))
sys.path.insert(0, str(R.parent / "ADAIR_wt_hook")); from ugv.geo import GZ_FRAME  # noqa: E402
sp = (O.parent / "segB_spawn.txt").read_text().split()[2].split(","); sx, sy = float(sp[0]), float(sp[1])
try:
    rd = json.load(open(S4 / f"ready_{tag}.json", encoding="utf-8"))[0]; px, py = GZ_FRAME.to_xy(rd["position"]["lat"], rd["position"]["lon"])
    rec["ready"] = {"state": rd["state"], "xy": [round(px, 2), round(py, 2)], "to_spawn_m": round(math.dist((px, py), (sx, sy)), 3), "profile_max_speed_kmh": rd["profile"]["max_speed_kmh"]}
    c["ready_within_2m"] = rd["state"] == "READY" and rec["ready"]["to_spawn_m"] <= 2.0
except Exception as e:  # noqa: BLE001
    rec["ready_error"] = repr(e); c["ready_within_2m"] = None
try:
    P = [json.loads(l) for l in open(O / f"poll_{tag}.jsonl", encoding="utf-8") if l.strip()]
    st = [(p["wall"], p["ugv"][0]) for p in P if p.get("ugv")]
    sims = [u.get("sim_time_s") for _, u in st]; ages = [round(wl - u["updated_at"], 3) for wl, u in st if u.get("updated_at")]
    rec["poll"] = {"n": len(P), "n_ok": len(st), "states": sorted({u["state"] for _, u in st}), "sim_first_last": [sims[0], sims[-1]] if sims else None,
                   "age_max_s": max(ages) if ages else None, "age_median_s": statistics.median(ages) if ages else None,
                   "speed_max": max((u.get("speed_mps") or 0) for _, u in st) if st else None}
    c["poll_ready_fresh"] = len(st) >= 40 and rec["poll"]["states"] == ["READY"] and sims[-1] > sims[0] and max(ages) <= 2.0
except Exception as e:  # noqa: BLE001
    rec["poll_error"] = repr(e); c["poll_ready_fresh"] = None
try:
    g = json.load(open(O / f"ground_{tag}.json", encoding="utf-8")); s = g["series"]
    rec["ground"] = {k: g[k] for k in ("n", "dz_min", "dz_max", "roll_abs_max", "pitch_abs_max", "tiles_seen")}
    settled = [x for x in s if x["t"] >= s[0]["t"] + 5.0]               # 처음 5 s (내려앉음) 제외
    rec["ground"]["settled_dz"] = [min(x["dz"] for x in settled), max(x["dz"] for x in settled)] if settled else None
    c["ground_contact"] = bool(settled) and all(abs(x["dz"]) <= 0.03 and abs(x["roll"]) <= 2.0 and abs(x["pitch"]) <= 2.0 for x in settled)
except Exception as e:  # noqa: BLE001
    rec["ground_error"] = repr(e); c["ground_contact"] = None
try:
    rows = list(csv.DictReader(open(O / f"probe_{tag}.csv"))); rt = [float(r["rtf"]) for r in rows if r["rtf"]]
    rec["perf"] = {"n": len(rows), "rtf_median": round(statistics.median(rt), 4) if rt else None, "rtf_min": round(min(rt), 4) if rt else None,
                   "mem_used_mb_max": max(int(r["mem_used_mb"]) for r in rows), "mem_before": (O / f"mem_before_{tag}.txt").read_text().strip(),
                   "flag_rtf_lt_0.5": bool(rt) and statistics.median(rt) < 0.5, "note": "특성 측정 — 합격 기준 아님"}
except Exception as e:  # noqa: BLE001
    rec["perf_error"] = repr(e)
try:
    rec["residual_after"] = int((O / f"residual_after_{tag}.txt").read_text().strip().splitlines()[-1]); c["residual0"] = rec["residual_after"] == 0
except Exception as e:  # noqa: BLE001
    rec["residual_error"] = repr(e); c["residual0"] = None
rec["checks"] = c
rec["status"] = "FAIL" if any(v is False for v in c.values()) else ("UNCONFIRMED" if any(v is None for v in c.values()) else "PASS")
json.dump(rec, open(O / f"envA_{tag}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(tag, rec["status"], c, json.dumps({k: rec.get(k) for k in ("ready", "poll", "ground", "perf")}, ensure_ascii=False))
