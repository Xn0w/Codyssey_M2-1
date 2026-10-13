# 진단 9 재분석 기록 (Codex 0650 4절) — 최초 자동 결과와 정정 결과
- 최초 자동 (chain_diag9.sh 그대로): slope_report.py --prefix d9_ → 중단 회차로 인식 안 됨 (태그에 'abort' 없음), slope5_judge.py (diag9 판, PFX d9_) → 태그에 '_on_' 없어 OFF 로 분류, 상태 RECORD — 제품 판정 없음 (chain_diag9.out 의 product= 빈칸).
- 정정 명령 (06:3x, ADAIR 루트):
  SLOPE_FORCE_ABORT_TAGS=d9_slope500_s0547_a .venv/Scripts/python.exe logs/ugv/stage6/diag9/slope_report_d9.py --prefix d9_ --logs ../ADAIR_wt_hook/logs/ugv --out <ADAIR>/logs/ugv/stage6/diag9/s4_slope_report.json
  S4_FORCE_ON=1 .venv/Scripts/python.exe logs/ugv/stage6/diag9/slope5_judge.py
- 분석기 sha1: 255febc9bef5f2ac819f676d4cdb53f0c0998857 (slope_report_d9.py — slope_report.py 와 차이: R 경로 parents[4], import os, aborted 판별에 SLOPE_FORCE_ABORT_TAGS), 151db2f583e825ae20273ad87f371e6fa50d4489 (slope5_judge.py diag9 판)
- 근거: 실행 계획(DIAG9_plan: ON 플래그·하강 중단), STOP_PATH 이벤트(speed_cap_first·stop_items_ramp 존재), road_test 중단 이벤트. 이 묶음은 ON 1회뿐이라 S4_FORCE_ON 이 OFF 를 ON 으로 읽을 위험 없음.
