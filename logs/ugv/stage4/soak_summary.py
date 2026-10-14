"""지속 운용 기록 요약: 출동·복귀 회수와 결과, 목표 교체·취소·고장 주입·해제, 서버 재시작 전후, 메모리·상태 파일 증가, 텔레메트리 지연, RTF,
정지 전 READY (Gazebo 실제 속도), 이탈·간격.
  python logs/ugv/stage4/soak_summary.py logs/ugv/fleet_soak_*.json
"""
import collections
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
cy = d.get("cycles", [])
res = collections.Counter((c.get("phase") or c.get("event"), c.get("status")) for c in cy)
print("기록", sys.argv[1])
print("주기 결과", dict(res))
errs = collections.Counter((c.get("error") or "")[:40] for c in cy if c.get("status") in ("FAILED",))
print("실패 사유", dict(errs))
m = d.get("metrics", [])
if m:
    mem = [x["server_mem_mb"] for x in m if x.get("server_mem_mb")]
    print("서버 메모리 MB 처음·최대·끝", mem[:1], max(mem) if mem else None, mem[-1:])
    st = m[-1].get("state_files_bytes")
    print("상태 파일 (끝)", st)
    print("텔레메트리 지연 최대", max(x.get("tel_age_max") or 0 for x in m), "교통 tick 최대 ms", max((x.get("tick_ms") or 0) for x in m))
print("재시작", json.dumps(d.get("restart"), ensure_ascii=False)[:1200])
a = d.get("analysis") or {}
for k, v in (a.get("vehicles") or {}).items():
    print(f"  {k}: 거리 {v.get('distance_m')} m, 이탈 {v.get('offroad_max_m')} ({v.get('offroad_events')}), 전복 {v.get('rollover')}, RTF {v.get('rtf')}")
gaps = [v.get("min_center_gap_minus_half_lengths_m") for v in (a.get("pairs") or {}).values()]
print("최소 간격", min(g for g in gaps if g is not None) if gaps else None, "겹침", sum((v.get("body_overlap_samples") or 0) for v in (a.get("pairs") or {}).values()))
print("명령 왕복", a.get("command_rtt_s"), "텔레메트리", a.get("telemetry_age_s"))
print("이상", d.get("anomalies", [])[:5])
