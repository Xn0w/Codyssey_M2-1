"""Gazebo 기록 전수: 정지 확인 전에 READY 였던 순간 (상태 READY 인데 속도 > 0.3 m/s) — fleet_*.json polls"""
import glob, json, sys
bad, n = [], 0
for f in sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else "logs/ugv/fleet_*_20261010_2[1-3]*.json")):
    d = json.load(open(f, encoding="utf-8"))
    for p in d.get("polls", []):
        for rid, v in p["vehicles"].items():
            n += 1
            if v["state"] == "READY" and (v["speed"] or 0) > 0.3:
                bad.append((f.split("\\")[-1].split("/")[-1], p["t"], rid, v["speed"], v["mission"]))
print("표본", n, "위반", len(bad))
for b in bad[:20]:
    print(b)
