# 재현: 저장소 루트에서 mock UAV(A-uav1) 를 8010 에 띄운 뒤 `.venv/bin/python docs/uav/evidence/2026-10-10_main/uav_cases.py out.json`
"""UAV 정상·거절 동작 재현 (mock, 포트 8010). 결과를 JSON 으로 남긴다."""
import json, time, sys, httpx
U = "http://127.0.0.1:8010"; R = "A-uav1"; c = httpx.Client(base_url=U, timeout=30)
T = {"lat": 38.0884, "lon": 128.1685, "alt_m_amsl": 570.0}   # 인제119(A 기지) 북쪽 약 3 km
out = []
def mock(**k): c.post("/mock/set", params=k)
def reset(): mock(battery_pct=100, wind_ms=3.1, failsafe=False, gps_ok=True, link_quality="OK")
def ev(name, **body):
    b = {"task_id": f"V-{name}", "decision_id": f"D-{name}", "target": T, "wind_ms": 3.1, "observation_type": "THERMAL"}; b.update(body)
    b = {k: v for k, v in b.items() if v is not None}
    r = c.post(f"/uav/{R}/evaluate", json=b); j = r.json()
    rec = {"case": name, "http": r.status_code, "verdict": j.get("verdict"), "reason": j.get("reason"), "eta_sec": j.get("eta_sec"),
           "counter_offer": j.get("counter_offer"), "warnings": (j.get("constraints") or {}).get("warnings"), "detail": j.get("detail")}
    out.append(rec); print(json.dumps(rec, ensure_ascii=False)); return j
def ex(name, **body):
    b = {"task_id": f"V-{name}", "decision_id": f"D-{name}", "target": T, "observation_type": "THERMAL", "observe_duration_s": 30}; b.update(body)
    r = c.post(f"/uav/{R}/execute", json=b); rec = {"case": name + ":execute", "http": r.status_code, "body": r.json()}
    out.append(rec); print(json.dumps(rec, ensure_ascii=False)); return r
reset()
# 정상: 평가 → 실행 → 완료까지
ev("N1_accept", observe_duration_s=30)
ex("N1_accept"); t0 = time.time()
ex("N1_accept")                                              # 같은 요청 재전송 → duplicate
ex("N1_accept", observe_duration_s=45)                      # 같은 키, 다른 내용 → 409
ev("R_busy")                                                 # 비행 중 다른 평가 → BUSY
while True:
    s = c.get(f"/uav/{R}/task/V-N1_accept").json()
    if s.get("status") in ("COMPLETED", "FAILED"): break
    time.sleep(1)
out.append({"case": "N1_accept:final", "wall_s": round(time.time() - t0, 1), "task": s}); print(json.dumps(out[-1], ensure_ascii=False)[:1500])
while c.get(f"/uav/{R}/state").json()["flight_mode"] not in ("HOLD", "LANDED") or c.get(f"/uav/{R}/state").json().get("returning_task_id"):
    time.sleep(1)
reset()
ev("R_wind_unknown", wind_ms=None)
ev("R_alt_unknown", target={"lat": T["lat"], "lon": T["lon"]})
ev("W_moderate_wind", wind_ms=9.0)
ev("R_high_wind", wind_ms=12.0)
ev("R_timeout", remaining_time_s=0)
ev("R_deadline_tight", remaining_time_s=30)
ev("R_capability", observation_type="LIDAR")
mock(failsafe=True); ev("R_failsafe"); reset()
mock(gps_ok=False); ev("R_gps"); reset()
mock(link_quality="LOST"); ev("R_link_lost"); reset()
mock(battery_pct=20); ev("C_counter_short_obs", observe_duration_s=600); reset()
mock(battery_pct=8); ev("R_low_battery"); reset()
ev("R_far_target", target={"lat": 37.60, "lon": 128.90, "alt_m_amsl": 300.0})
# 중단: 실행 직후 abort
ev("A_abort"); ex("A_abort"); time.sleep(0.5)
r = c.post(f"/uav/{R}/task/V-A_abort/abort", json={"reason": "OPERATOR"}); out.append({"case": "A_abort:abort", "http": r.status_code, "body": r.json()}); print(json.dumps(out[-1], ensure_ascii=False))
r = c.post(f"/uav/{R}/task/V-A_abort/abort", json={"reason": "OPERATOR"}); out.append({"case": "A_abort:abort_again", "http": r.status_code, "body": r.json()}); print(json.dumps(out[-1], ensure_ascii=False))
r = c.get(f"/uav/B-uav9/state"); out.append({"case": "R_wrong_id", "http": r.status_code}); print(out[-1])
json.dump({"run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "server": U, "mode": "mock", "cases": out}, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
