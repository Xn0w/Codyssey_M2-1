# plan_offline.sh 와 같은 조건(sim 드라이버, 같은 차량·도로 부분집합·목표)으로 서버 앱을 포트 없이(TestClient) 띄워 /route 저장
# 사용: python plan_inproc.py <소스 트리> <out.json> <state dir>  (환경 FLEET_SIM=<sim 차량 json>, TARGET_NODE=<RP:도로:s> 로 바꿀 수 있음)
import os, sys, json, time, shutil
src, out, state = sys.argv[1], sys.argv[2], sys.argv[3]
M = r"C:\Users\수다쟁이고양이들\Documents\GitHub\ADAIR"
D = M + r"\logs\ugv\stage6\corner494862"
shutil.rmtree(state, ignore_errors=True)
os.environ.update(UGV_DRIVER="sim", UGV_VEHICLES_JSON=os.environ.get("FLEET_SIM") or D + r"\fleet_c_sim.json",
                  UGV_ROAD_SUBSET=M + r"\logs\ugv\stage5\tiles_v2c1\road_subset_ab_route_v1.json",
                  UGV_TIME_SCALE="1", UGV_LAT_ACCEL="1.0", UGV_ALLOW_NO_FIRE_DATA="1", UGV_STATE_DIR=state)
sys.path.insert(0, src)
os.chdir(src)
import ugv, ugv.roads
assert os.path.abspath(ugv.__file__).startswith(os.path.abspath(src)), ugv.__file__
from fastapi.testclient import TestClient
from ugv.server import app
with TestClient(app) as c:
    for _ in range(90):
        if '"state":"READY"' in c.get("/ugv", headers={"X-ADAIR-Monitor": "1"}).text.replace(" ", ""):
            break
        time.sleep(1)
    K = f"PLAN-inproc-{int(time.time())}"
    b = {"task_id": K, "decision_id": "D-" + K, "target_node": os.environ.get("TARGET_NODE") or "RP:682500789:49.1"}
    e = c.post("/ugv/A-ugv1/evaluate", json=b).json()
    x = c.post("/ugv/A-ugv1/execute", json=b).json()
    time.sleep(1)
    r = c.get("/ugv/A-ugv1/route").json()
    r["evaluate"] = {k: e.get(k) for k in ("verdict", "eta_sec", "reason", "detail", "approach")}
open(out, "w", encoding="utf-8").write(json.dumps(r, ensure_ascii=False))
print("saved", out, "eta", r.get("eta_sec"), "n", len(r.get("plan_xy") or []), "eval_eta", e.get("eta_sec"), "src", ugv.__file__)
