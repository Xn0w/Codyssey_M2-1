"""대상 집합 2: fleet_ab 4 쌍 양방향 — ab_eval.py 를 기록 장치를 켠 채 실행. 사용 (트리에서): python ab_dump.py <tiles> <ab_out.json>"""
import os, runpy, sys
sys.path[:0] = [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]
# ab_eval 이 넣는 환경(도로 부분집합)을 계획기 import 전에 먼저 넣는다 — 순서가 뒤면 config.ROAD_SUBSET 이 빈 값으로 굳어 전체 도로망으로 계획 (2026-10-14 첫 덤프 무효)
os.environ["UGV_ROAD_SUBSET"] = str(__import__('pathlib').Path(sys.argv[1]) / "road_subset_all_included.json"); os.environ.setdefault("UGV_ALLOW_NO_FIRE_DATA", "1")
import eta_dump_plugin as P
P._instrument()
ab = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s6diag", "ab_eval.py")
sys.argv = [ab] + sys.argv[1:]
runpy.run_path(ab, run_name="__main__")
