"""R2 저속 통과 구동기 (WSL, Codex 0920 3절, NO_PX4 회차 전용). /model/<model>/command/motor_speed (gz.msgs.Actuators, velocity[0] rad/s
— 모델 JointController 4 개가 actuator 0 을 네 바퀴 속도로 그대로 씀, 축 +y → 양수 = 전진). 조향 명령 없음 (servo_0 미발행 → 위치 목표 0).
sim 시각 (/world/<world>/clock) 기준: 첫 수신 + settle_s 까지 0, 그 뒤 drive_s 동안 omega (앞뒤 ramp_s 2 s 선형), 그 뒤 0 을 끝까지. 50 Hz 발행, 발행 기록 CSV (wall, sim, cmd)."""
import argparse, csv, signal, sys, threading, time
from gz.msgs10.actuators_pb2 import Actuators
from gz.msgs10.clock_pb2 import Clock
from gz.transport13 import Node
ap = argparse.ArgumentParser()
ap.add_argument("--world", required=True); ap.add_argument("--model", default="adair_ugv_1"); ap.add_argument("--out", required=True)
ap.add_argument("--omega", type=float, default=1.0 / 0.35); ap.add_argument("--settle_s", type=float, default=5.0); ap.add_argument("--drive_s", type=float, default=15.0)
ap.add_argument("--total_s", type=float, default=60.0); ap.add_argument("--ramp_s", type=float, default=2.0)
a = ap.parse_args()
sim = [None]; lock = threading.Lock()
def on_clock(m):
    with lock: sim[0] = m.sim.sec + m.sim.nsec * 1e-9
node = Node(); node.subscribe(Clock, f"/world/{a.world}/clock", on_clock)
pub = node.advertise(f"/model/{a.model}/command/motor_speed", Actuators)
stop = [False]; signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__(0, True))
f = open(a.out, "w", newline=""); w = csv.writer(f); w.writerow(["wall", "sim", "cmd_rad_s", "phase"])
t_first = None; t0 = time.time()
while not stop[0] and time.time() - t0 < a.total_s:
    with lock: s = sim[0]
    if s is not None and t_first is None: t_first = s
    if s is None: cmd, ph = 0.0, "wait_clock"
    elif s < t_first + a.settle_s: cmd, ph = 0.0, "settle"
    elif s < t_first + a.settle_s + a.drive_s:                       # 2 s 선형 가속·끝 2 s 선형 감속 (속도 모드 계단 명령의 충격으로 자세 중단 신호가 나는 것 방지)
        u = s - (t_first + a.settle_s); r = min(1.0, u / a.ramp_s, (a.drive_s - u) / a.ramp_s); cmd, ph = a.omega * max(0.0, r), "drive"
    else: cmd, ph = 0.0, "hold"
    m = Actuators(); m.velocity.append(cmd); pub.publish(m)
    w.writerow([round(time.time(), 3), None if s is None else round(s, 4), round(cmd, 4), ph]); time.sleep(0.02)
for _ in range(10):
    m = Actuators(); m.velocity.append(0.0); pub.publish(m); time.sleep(0.02)
f.close(); print("r2_drive done", t_first); sys.stdout.flush()
import os; os._exit(0)
