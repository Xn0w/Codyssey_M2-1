# -*- coding: utf-8 -*-
"""chain_ft4b 게이트 2 — 5 cm 뒤판 결과(1차 13:46)를 본 뒤 예측 확인 방식을 사후 수정한 것 (결과 전 고정 아님). 성능 합격 기준(정적 5회 PASS)은 불변. 출력 gate2.json (1차 gate.json·gate_run1_*.json 보존) (후속 계획 '강성 분석 후속 피드백 재검토' — 결과 전 고정 2026-10-13 13:05):
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
    if w == "diag5ft2r" and v is not None and not res[w]["in_range"] and v > p and r:
        # ft4 1차(13:46) 원인 확인: 5 cm 뒤판에서 차체가 롤해(0.0061 rad) 뒤축 Δq = 0.039 m < 판 높이 → 예측식의 '롤 0·Δq = h' 가정 불성립,
        # 하중이 대각 앞바퀴로 나뉘어 비율이 예측보다 좋다. 이 경우 강성 예측(유효 700 kN/m)을 직접 확인: 뒤축 Δfn/Δq 가 ±5 % 안이면 설명된 차이로 진행
        fn, q = r["fn_median_N"], r["susp_q_eq_m"]
        dq = abs(q["susp_rear_left"] - q["susp_rear_right"])
        keff = abs(fn["wheel_rear_left"] - fn["wheel_rear_right"]) / dq if dq > 0.005 else None
        res[w]["explained"] = {"reason": "롤 0 가정 불성립 (Δq < 판 높이), 비율이 예측보다 좋은 방향", "rear_dq_m": round(dq, 4),
                               "plate_h_m": 0.05, "body_roll_mean_rad": r.get("body_roll_mean_rad"), "body_pitch_mean_rad": r.get("body_pitch_mean_rad"),
                               "fn_N": {k: round(v, 1) for k, v in fn.items()},
                               "front_lr_diff_N": round(fn["wheel_front_left"] - fn["wheel_front_right"], 1),
                               "rear_lr_diff_N": round(fn["wheel_rear_left"] - fn["wheel_rear_right"], 1),
                               "flat_ref_fn_N": (by.get("ft-fire_v2b_adair_flat_susp") or {}).get("fn_median_N"),
                               "rear_keff_N_per_m": None if keff is None else round(keff), "keff_pred": 700000,
                               "keff_within_5pct": keff is not None and abs(keff - 700000) / 700000 <= 0.05}
        res[w]["in_range"] = res[w]["explained"]["keff_within_5pct"]
    ok &= res[w]["in_range"]
res["proceed"] = bool(ok)
(D / "gate2.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False))
sys.exit(0 if ok else 1)
