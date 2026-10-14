"""진단 7 gz 쪽 기록기 (Codex 0540 3절): 한 실행 동안 gz-transport 를 직접 구독해 sim stamp 와 수신 wall 시각을 함께 CSV 로.
WSL python3 (gz.transport13 / gz.msgs10). 사용:
  python3 gz_rec.py --world W --model adair_ugv_3 --out DIR --duration 400
기록: imu.csv (header stamp, 선형 가속도 xyz, 각속도 xyz, 자세 q), pose.csv (pose/info 중 그 모델 — header stamp, 위치, 자세),
joint.csv (바퀴 관절 이름·위치·속도 — header stamp), cmd.csv (/model/<m>/command/motor_speed Actuators — header stamp, velocity[0]),
meta.json (토픽·수신 개수·시작/끝, 실제 수신 주기 통계). 버퍼 쓰기, SIGTERM/시간 만료 때 flush. 보간·재표본 없음."""
import argparse
import json
import os
import signal
import sys
import threading
import time

from gz.msgs10.actuators_pb2 import Actuators
from gz.msgs10.imu_pb2 import IMU
from gz.msgs10.model_pb2 import Model
from gz.msgs10.pose_v_pb2 import Pose_V
from gz.transport13 import Node

ap = argparse.ArgumentParser()
ap.add_argument("--world", required=True); ap.add_argument("--model", required=True)
ap.add_argument("--out", required=True); ap.add_argument("--duration", type=float, default=400.0)
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
W, M = a.world, a.model
topics = {"imu": f"/world/{W}/model/{M}/link/base_link/sensor/imu_sensor/imu", "pose": f"/world/{W}/pose/info",
          "joint": f"/world/{W}/model/{M}/joint_state", "cmd": f"/model/{M}/command/motor_speed"}
files = {k: open(os.path.join(a.out, f"{k}.csv"), "w", buffering=1 << 20) for k in topics}
files["imu"].write("stamp,wall,ax,ay,az,gx,gy,gz,qw,qx,qy,qz\n")
files["pose"].write("stamp,wall,x,y,z,qw,qx,qy,qz\n")
files["joint"].write("stamp,wall,name,pos,vel\n")
files["cmd"].write("stamp,wall,v0,n\n")
count = {k: 0 for k in topics}
lock = threading.Lock()


def st(h):
    return h.stamp.sec + h.stamp.nsec * 1e-9


def on_imu(m):
    w = time.time()
    with lock:
        count["imu"] += 1
        la, av, q = m.linear_acceleration, m.angular_velocity, m.orientation
        files["imu"].write(f"{st(m.header):.6f},{w:.6f},{la.x:.5f},{la.y:.5f},{la.z:.5f},{av.x:.5f},{av.y:.5f},{av.z:.5f},{q.w:.6f},{q.x:.6f},{q.y:.6f},{q.z:.6f}\n")


def on_pose(m):
    w = time.time()
    for p in m.pose:
        if p.name == M:
            with lock:
                count["pose"] += 1
                files["pose"].write(f"{st(m.header):.6f},{w:.6f},{p.position.x:.5f},{p.position.y:.5f},{p.position.z:.5f},"
                                    f"{p.orientation.w:.6f},{p.orientation.x:.6f},{p.orientation.y:.6f},{p.orientation.z:.6f}\n")
            break


def on_joint(m):
    w = time.time()
    with lock:
        count["joint"] += 1
        s = st(m.header)
        for j in m.joint:
            if "wheel" in j.name and "steering" not in j.name:
                files["joint"].write(f"{s:.6f},{w:.6f},{j.name},{j.axis1.position:.5f},{j.axis1.velocity:.5f}\n")


def on_cmd(m):
    w = time.time()
    with lock:
        count["cmd"] += 1
        files["cmd"].write(f"{st(m.header):.6f},{w:.6f},{(m.velocity[0] if len(m.velocity) else float('nan')):.5f},{len(m.velocity)}\n")


node = Node()
ok = {"imu": node.subscribe(IMU, topics["imu"], on_imu), "pose": node.subscribe(Pose_V, topics["pose"], on_pose),
      "joint": node.subscribe(Model, topics["joint"], on_joint), "cmd": node.subscribe(Actuators, topics["cmd"], on_cmd)}
t0 = time.time()
stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *x: stop.set())
signal.signal(signal.SIGINT, lambda *x: stop.set())
while not stop.is_set() and time.time() - t0 < a.duration:
    time.sleep(0.5)
with lock:
    for f in files.values():
        f.flush(); f.close()
json.dump({"topics": topics, "subscribed": ok, "count": count, "start_wall": t0, "end_wall": time.time(),
           "partition": os.getenv("GZ_PARTITION")}, open(os.path.join(a.out, "meta.json"), "w"), indent=1)
print("gz_rec done", count, ok, file=sys.stderr)
