# -*- coding: utf-8 -*-
"""chain_ft4 중간 게이트 (후속 계획 '강성 분석 후속 피드백 재검토' — 결과 전 고정 2026-10-13 13:05):
fire_v2b 정적 회차를 S3 9절 예측과 대조. 크게 어긋나면 주행(요철·회전) 전에 보류하고 원인 분석.
  평지 뒤축 q 예측 0.025 m → 허용 0.0175~0.0325 m (±30 %)
  뒤판 5 cm 최소 하중/축 평균 예측 0.546 → 허용 ±0.05, 2 cm 0.818 → ±0.05
  앞판 2/5 cm 예측 0.835/0.587 (불변) → ±0.03
  정적 회차 무효 표시(.invalid·.contaminated·.invalid_evidence·.invalid_stop)가 있으면 보류
출력: logs/ugv/stage6/susp_static_ft4/gate.json, 종료 코드 0 = 진행, 1 = 보류.
(A) 정적 필수 5회 모두 판정기 PASS (기존 기준) 와 (B) 예측 범위 일치(평지 뒤축 각 바퀴·좌우 차 ≤ 3 mm, 판 하중)를 따로 검사 — 둘 다 만족해야 주행."""
import json
import sys
from pathlib import Path

D = Path(__file__).resolve().parent / "susp_static_ft4"
rep = json.loads((D / "report_ssr2.json").read_text(encoding="utf-8"))
by = {r["tag"]: r for r in rep}
pred = {"flat_rear_q": (0.025, 0.0075), "diag2ft2r": (0.818, 0.05), "diag5ft2r": (0.546, 0.05), "diag2ft2": (0.835, 0.03), "diag5ft2": (0.587, 0.03)}
res, ok = {}, True
for mk in (".invalid", ".contaminated", ".invalid_evidence", ".invalid_stop"):
    bad = sorted(p.name for p in D.glob(f"*{mk}"))
    if bad:
        res[f"markers{mk}"] = bad
        ok = False
# (A) 정적 합격: 필수 5회가 모두 있고 판정기 상태 PASS (기존 기준 — 예측 범위 안이어도 기준 불합격이면 보류). 2026-10-13 추가 보완 1
need = ["ft-fire_v2b_adair_flat_susp", "ft-fire_v2b_adair_flat_diag2ft2r", "ft-fire_v2b_adair_flat_diag5ft2r", "ft-fire_v2b_adair_flat_diag2ft2", "ft-fire_v2b_adair_flat_diag5ft2"]
res["static_pass"] = {t: (by[t].get("status") if t in by else "없음") for t in need}
ok &= all(v == "PASS" for v in res["static_pass"].values())
# (B) 예측 일치: 평지 뒤축 q 각 바퀴가 예측 범위 안 + 뒤축 좌우 차 ≤ 3 mm
f = by.get("ft-fire_v2b_adair_flat_susp")
if f:
    ql, qrr = f["susp_q_eq_m"].get("susp_rear_left"), f["susp_q_eq_m"].get("susp_rear_right")
    p0, tol = pred["flat_rear_q"]
    each = {"rear_left": ql, "rear_right": qrr}
    res["flat_rear_q"] = {"measured_each": each, "pred": p0, "tol": tol,
                          "each_in_range": all(v is not None and abs(v - p0) <= tol for v in each.values()),
                          "lr_diff_m": None if None in each.values() else round(abs(ql - qrr), 5)}
    res["flat_rear_q"]["lr_diff_le_3mm"] = res["flat_rear_q"]["lr_diff_m"] is not None and res["flat_rear_q"]["lr_diff_m"] <= 0.003
    ok &= res["flat_rear_q"]["each_in_range"] and res["flat_rear_q"]["lr_diff_le_3mm"]
else:
    res["flat_rear_q"] = "평지 회차 없음"
    ok = False
for w in ("diag2ft2r", "diag5ft2r", "diag2ft2", "diag5ft2"):
    r = by.get(f"ft-fire_v2b_adair_flat_{w}")
    v = None if r is None else r.get("min_fn_over_axle_mean")
    p, tol = pred[w]
    res[w] = {"measured": v, "pred": p, "in_range": v is not None and abs(v - p) <= tol}
    ok &= res[w]["in_range"]
res["proceed"] = bool(ok)
(D / "gate.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False))
sys.exit(0 if ok else 1)
