"""final_judge.py 분류 확인 (Codex 0650 4절 — 물리 시험 없이): 지난 회차 묶음에 final_judge 를 그 묶음 폴더 기준으로 돌려
ON/OFF·중단 분류와 상태를 출력. 사용 (ADAIR 루트): python logs/ugv/stage6/final500/judge_class_check.py <prefix> <stage6 하위 폴더>"""
import os, sys
from pathlib import Path
pfx, sub = sys.argv[1], sys.argv[2]
os.environ["S4_PREFIX"] = pfx
os.environ["S4_SR"] = str(Path("logs/ugv/stage6") / sub / "s4_slope_report.json")
f = Path("logs/ugv/stage6/final7/final_judge_v7_1.py")
src = f.read_text(encoding="utf-8").replace('O = R / "logs/ugv/stage6/final7"', f'O = R / "logs/ugv/stage6/{sub}"')
src = src.replace('json.dump({"off_min": OFF_MIN, "runs": res}, open(O / f"{PFX}judge.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)',
                  'pass  # 확인용: 원래 판정 파일을 덮지 않음')
exec(compile(src, str(f), "exec"), {"__file__": str(f.resolve()), "__name__": "__main__"})
