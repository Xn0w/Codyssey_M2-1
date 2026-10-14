"""v7.1 0g 산술 확인 (Codex 0713) — final_judge_v7_1.needed_rule_ok 만 떼어 시험 (Gazebo·pytest 없음)."""
import ast
from pathlib import Path
src = Path(__file__).with_name("final_judge_v7_1.py").read_text(encoding="utf-8")
fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "needed_rule_ok")
ns = {}; exec(compile(ast.Module([fn], []), "needed_rule_ok", "exec"), ns); f = ns["needed_rule_ok"]
cases = [((9.45, 34.7), True), ((9.45, 34.8), True), ((9.45, 34.6), False), ((9.45, 34.9), False),
         ((None, 34.7), None), ((9.45, None), None), ((float("nan"), 34.7), False), ((9.45, float("inf")), False),
         ((float("inf"), 34.7), False), ((9.455, 34.8), False), ((9.45, 34.75), False), (("x", 34.7), False),
         ((9.49, 35.0), True), ((9.48, 35.0), True), ((8.17, 27.2), True)]
bad = 0
for (a, b), want in cases:
    got = f(a, b); ok = got is want; bad += not ok
    print(f"{a!s:>6} {b!s:>6} -> {got!s:5} want {want!s:5} {'OK' if ok else 'MISMATCH'}")
print("ALL_OK" if bad == 0 else f"MISMATCH {bad}")
