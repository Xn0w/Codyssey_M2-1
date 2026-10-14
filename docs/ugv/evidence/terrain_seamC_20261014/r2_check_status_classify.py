"""r2_check 상태 분류 확인 (Codex 0940 1절): 원본 (v1) 과 정정본 (v1.1) 의 체크 → 상태 규칙을 None·numpy False·numpy True·Python bool 로 비교."""
import numpy as np
def v1(c): return "FAIL" if any(v is False for v in c.values()) else ("UNCONFIRMED" if any(v is None for v in c.values()) else "PASS")
def v11(c):
    c = {k: (None if v is None else bool(v)) for k, v in c.items()}; return v1(c)
cases = {"np_False": {"a": True, "b": np.bool_(False)}, "py_False": {"a": True, "b": False}, "None": {"a": True, "b": None},
         "np_True": {"a": np.bool_(True), "b": True}, "all_True": {"a": True, "b": True}, "np_False_and_None": {"a": np.bool_(False), "b": None}}
for k, c in cases.items(): print(f"{k:18s} v1={v1(c):12s} v1.1={v11(c)}")
