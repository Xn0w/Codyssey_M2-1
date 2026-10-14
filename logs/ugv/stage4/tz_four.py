"""6단계 ⑤: 지형 타일 구역 4대 동시 운용 (B 차량 2대는 시험 배치 — 소속을 A 대기 위치 2·3 으로). 각자 다른 구역 안 목표 → 대기 위치 복귀.
  UGV_GZ_WORLD=tz_a33 python logs/ugv/stage4/tz_four.py --track-s 1500"""
import argparse, sys, time
sys.path.insert(0, ".")
from ugv.tools import fleet_test

JOBS = [("A-ugv1", "Z4-AU", "RP:682501271:39.7"), ("A-fire1", "Z4-AF", "RP:682501110:48.9"),
        ("B-ugv1", "Z4-BU", "RP:682503138:82.9"), ("B-fire1", "Z4-BF", "RP:682502054:62.7")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track-s", type=float, default=1500)
    a = ap.parse_args()
    run = fleet_test.Run("tz_four", a.track_s, rids=[j[0] for j in JOBS])
    started = []
    for rid, key, node in JOBS:
        if run.go(rid, key, node=node)["status_code"] == 200:
            started.append((rid, key))
        time.sleep(1)
    run.wait(started, a.track_s * 0.45)
    homes = []
    for rid, key in started:
        if run.home(rid, "H-" + key)["status_code"] == 200:
            homes.append((rid, "H-" + key))
        time.sleep(1)
    run.wait(homes, a.track_s * 0.45)
    run.finish()


if __name__ == "__main__":
    main()
