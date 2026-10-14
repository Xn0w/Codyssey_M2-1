# -*- coding: utf-8 -*-
"""S4 명령 기준 제동 요약: python s4_summary.py <report_vdr2.json>  (vehicle_drive_report --out 결과)
회차마다 정지 방식·정차 유지 정책·명령 때 속도·계획 정지거리·실제(명령→정지)·계획 정지점 통과 속도·정지점 초과·판정."""
import json
import sys
from collections import defaultdict

rows = json.load(open(sys.argv[1], encoding="utf-8"))
grp = defaultdict(list)
for r in rows:
    if not r["scenario"].startswith(("cancel", "estop")):
        continue
    cb = r.get("command_brake") or {}
    pol = "server" if str(cb.get("park_policy", "")).startswith("server") else "PX4단독"
    grp[(r["model"], r["variant"], r["scenario"], pol)].append((r["rep"], r["status"], cb))
for k in sorted(grp):
    print(f"## {k[0]} {k[1]} {k[2]} 정차정책={k[3]}")
    for rep, st, cb in sorted(grp[k]):
        print(f"  {rep:3s} {st:10s} v0 {cb.get('speed_at_command_mps')} m/s | 계획 {cb.get('planned_stop_dist_m')} m | 실제 {cb.get('cmd_to_stop_m')} m"
              f" ({cb.get('cmd_to_stop_s')} s) | 감속 시작 {cb.get('cmd_to_decel_s')} s | 정지점 통과 {cb.get('speed_at_planned_point_mps')} m/s"
              f" @{cb.get('cmd_to_planned_point_s')} s | 정지점 초과 {cb.get('stop_vs_planned_point_m')} m | 재이동 {cb.get('re_motion_after_stop')}"
              f" | {str(cb.get('park_policy', ''))[:24]}")
