"""타일 구역 월드 스폰: 구역 도로 부분집합 기준 거점 대기 위치(서버와 같은 규칙, ugv.tools.spawn_pose --fleet) + 지형 높이.
  UGV_ROAD_SUBSET=logs/ugv/stage5/tiles/road_subset_<world>.json python logs/ugv/stage4/tz_spawn.py <fleet.json> <out spawn> [시험 배치 initial 은 그대로]"""
import json, math, subprocess, sys
sys.path.insert(0, ".")
from ugv.tools.build_terrain_tiles import Surface
from ugv.geo import FRAME
from ugv.profiles import get
fleet, out = sys.argv[1], sys.argv[2]
cfgs = json.load(open(fleet, encoding="utf-8"))
r = subprocess.run([sys.executable, "-m", "ugv.tools.spawn_pose", "--fleet", fleet], capture_output=True, text=True)
lines = {l.split()[3]: l.split() for l in r.stdout.splitlines() if l.strip()}
S = Surface()
Z = {"adair_ugv": 0.45, "adair_firetruck": 0.65}
res = []
for c in cfgs:
    rid, prof = c["resource_id"], c.get("profile", "adair_ugv")
    if isinstance(c.get("initial"), dict):                      # 시험 배치
        x, y = FRAME.to_xy(c["initial"]["lat"], c["initial"]["lon"])
        yaw = math.radians(90.0 - c["initial"]["heading_deg"])
        inst, model = c["px4"]["instance"], get(prof).gz_model
    else:
        inst, model, pose = lines[rid][0], lines[rid][1], lines[rid][2]
        x, y, _, yaw = map(float, pose.split(","))
    res.append(f"{inst} {model} {x:.2f},{y:.2f},{S.z(x, y) - 172.1 + Z[prof]:.3f},{yaw:.4f} {rid}")
open(out, "w").write("\n".join(res) + "\n")
print("\n".join(res)); print(r.stderr.strip())
