"""4단계: 총괄 통신 단절 실제 벽시계 시험 (Gazebo PX4, 시간 배율 1). 총괄 연락은 처음 실행 요청 한 번뿐이고, 그 뒤 감시는
X-ADAIR-Monitor 머리표로만 한다 (연락으로 세지 않음). 기대: 마지막 연락 600 s 뒤 진행 임무 취소·도로 따라 정지(STOPPED),
정지 확인 1800 s 뒤 소속 거점 복귀 시도(RETURNING) → 도착(RETURNED)·READY. COM_DL_LOSS_T(PX4 링크) 와는 별개다.
  python logs/ugv/stage4/comm_loss_wall.py --rid A-ugv1 --target 37.9650816 128.3175278 --track-s 3900
기록: logs/ugv/stage4/comm_loss_wall_<시각>.json
"""
import argparse
import json
import pathlib
import time

import httpx

OUT = pathlib.Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8100")
    ap.add_argument("--rid", default="A-ugv1")
    ap.add_argument("--target", nargs=2, type=float, required=True)
    ap.add_argument("--track-s", type=float, default=3900)
    ap.add_argument("--every", type=float, default=4.0)   # uvicorn 유휴 연결 종료(5 s)와 겹치지 않게 (5 s 주기에서 연결 끊김 오류로 시험이 멈췄다)
    a = ap.parse_args()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    mon = httpx.Client(base_url=a.url, timeout=30, headers={"X-ADAIR-Monitor": "1"})
    key = f"CL-{stamp}"
    body = {"task_id": key, "decision_id": "D-" + key, "target": {"lat": a.target[0], "lon": a.target[1]}}
    t_contact = time.time()
    ev = httpx.post(f"{a.url}/ugv/{a.rid}/evaluate", json=body, timeout=120).json()      # 총괄 연락 (머리표 없음)
    if ev.get("target_node"):
        body["target_node"] = ev["target_node"]["node_id"]
    t_contact = time.time()
    r = httpx.post(f"{a.url}/ugv/{a.rid}/execute", json=body, timeout=120)               # 마지막 총괄 연락
    t_contact = time.time()
    log = {"stamp": stamp, "rid": a.rid, "target": a.target, "evaluate": ev, "execute": {"status": r.status_code, "body": r.json()},
           "last_contact_wall": t_contact, "timeline": [], "phases": {}}
    print("실행", r.status_code, r.json().get("status"), "ETA", ev.get("eta_sec"), flush=True)
    end = t_contact + a.track_s
    last_phase = None
    def get(path):
        for k in range(5):                                   # 감시 요청은 연결 오류면 다시 (서버 상태와 무관한 연결 끊김)
            try:
                return mon.get(path).json()
            except httpx.TransportError as e:
                log.setdefault("transport_errors", []).append({"t": round(time.time() - t_contact, 1), "path": path, "error": str(e)[:120]})
                time.sleep(0.5)
        raise RuntimeError(f"감시 요청 5번 실패: {path}")
    while time.time() < end:
        st = get(f"/ugv/{a.rid}/state")
        tk = get(f"/ugv/{a.rid}/task/{key}") if st else {}
        el = round(time.time() - t_contact, 1)
        rec = {"t": el, "state": st["state"], "mission": st["mission_state"], "speed": st["speed_mps"],
               "comm": st["comm"].get("phase"), "silence": st["comm"].get("orchestrator_silence_s"),
               "task": st["current_task_id"], "task_status": tk.get("status"), "task_error": tk.get("error"),
               "pos": [st["position"]["lat"], st["position"]["lon"]], "node": st["current_node"], "fault": st["fault"]}
        log["timeline"].append(rec)
        if rec["comm"] != last_phase:
            log["phases"][rec["comm"]] = el
            print(f"[{el:7.1f}] 통신 단계 {last_phase} → {rec['comm']} (상태 {rec['state']}/{rec['mission']}, 속도 {rec['speed']})",
                  flush=True)
            last_phase = rec["comm"]
        if int(el) % 60 < a.every:
            (OUT / f"comm_loss_wall_{stamp}.partial.json").write_text(json.dumps(log, ensure_ascii=False), encoding="utf-8")
            print(f"[{el:7.1f}] {rec['state']}/{rec['mission']} 속도 {rec['speed']} 통신 {rec['comm']} 침묵 {rec['silence']} "
                  f"임무 {rec['task_status']}", flush=True)
        if rec["comm"] == "RETURNED" and rec["state"] == "READY" and (rec["speed"] or 0) < 0.1:
            log["returned_ready_t"] = el
            break
        time.sleep(a.every)
    log["events"] = get(f"/ugv/{a.rid}/events?limit=200")
    p = OUT / f"comm_loss_wall_{stamp}.json"
    p.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print("기록:", p, "단계", log["phases"])


if __name__ == "__main__":
    main()
