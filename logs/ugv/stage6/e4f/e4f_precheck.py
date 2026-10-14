"""E4f 진입 전 읽기 전용 확인 (Codex 0728): 이번 chain_final7r 과 연결된 f7 판정 JSON 에서 사례별 고유 태그 PASS 3회·총 6회,
회차별 래퍼 rc·오염 표식, 회차 로그의 FINAL7R_RESULT, 경사 동결 해시 (FINAL7R_freeze.sha1) 대조. 통과 시 'PRECHECK_OK', 아니면 'PRECHECK_HOLD <이유>'."""
import hashlib, json, re, sys
from pathlib import Path
R = Path(__file__).resolve().parents[4]; F = R / "logs/ugv/stage6/final7"; S4 = R / "logs/ugv/stage4"
bad = []
d = json.load(open(F / "f7_judge.json", encoding="utf-8"))
runs = [r for r in d["runs"] if r["tag"].startswith("f7_on_")]
ok = {c: sorted({r["tag"] for r in runs if r["case"] == c and r["status"] == "PASS"}) for c in ("s3113", "s0547")}
nonpass = [(r["tag"], r["status"]) for r in runs if r["status"] != "PASS"]
if nonpass: bad.append(f"비PASS {nonpass}")
for c, t in ok.items():
    if len(t) != 3: bad.append(f"{c} PASS {len(t)}≠3")
log = (F / "run.out").read_text(encoding="utf-8", errors="replace")
for c, ts in ok.items():
    for t in ts:
        try:
            w = json.load(open(S4 / f"rc_{t}.json", encoding="utf-8"))
            if not (w.get("test_rc") == 0 and w.get("copy_logs_rc") == 0 and str(w.get("stop_post_rc")) == "0" and w.get("invalid_stop") is False):
                bad.append(f"{t} rc {w}")
        except Exception as e:  # noqa: BLE001
            bad.append(f"{t} rc 파일 {e!r}")
        if any((S4 / f"{t}.{m}").exists() for m in ("contaminated", "invalid_evidence", "invalid_stop")): bad.append(f"{t} 표식")
        if t == "f7_on_s3113_downabort_1":   # v7 최초 FAIL → v7.1 정정 후 인정 (Codex 0713)
            if not (re.search(rf"FINAL7_RESULT {t} FAIL", log) and (F / "f7_judge_v7_ORIGINAL_run1.json").exists()): bad.append(f"{t} 정정 이력 누락")
        elif not re.search(rf"FINAL7R_RESULT {t} PASS", log): bad.append(f"{t} 회차 로그 FINAL7R_RESULT PASS 없음")
for ln in (F / "FINAL7R_freeze.sha1").read_text(encoding="utf-8").splitlines():
    h, name = ln.split(" *", 1)
    try:
        if hashlib.sha1((F / name).read_bytes()).hexdigest() != h: bad.append(f"해시 불일치 {name}")
    except Exception as e:  # noqa: BLE001
        bad.append(f"해시 파일 {name} {e!r}")
print("PRECHECK_OK " + json.dumps(ok) if not bad else "PRECHECK_HOLD " + " | ".join(bad))
