"""A↔B 실제 지형 월드 범위 명세 (Codex 0130 4절 1~3, 준비 단계 — 월드 생성·Gazebo 기동 없음).
실행 (서버 트리 ADAIR_wt_integ 에서): python route_tile_union.py <tiles_dir> <out.json>
- 네 경로(UGV·소방차 × A→B/B→A)를 ab_eval 과 같은 조건(road_subset_all_included, target_node = 상대 거점 출입점)으로 계획·실행해 전체 선형을 얻는다.
- 경로 점마다 반경 BUF_M(도로 반폭 + 차체 + 여유) 안에 닿는 타일 = 필수, 그 이웃 8 칸 = 이음매·경계 처리용 인접 타일.
- 정지 경로·끝 지점 연장·출발 대기는 경로 끝 ±STOP_M 를 같은 타일 판정에 포함 (경로 선형 위 — 안전 정지 경로는 같은 도로라 선형 근처).
출력: 경로별·합집합 타일 목록, 누락(tiles.json 에 없는 칸), 면적, 디스크(타일 폴더 크기 합), 메모리 추정 근거, 출처 해시."""
import asyncio
import hashlib
import json
import math
import os
import pathlib
import sys
import tempfile

tiles = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2])
os.environ["UGV_ROAD_SUBSET"] = str(tiles / "road_subset_all_included.json"); os.environ.setdefault("UGV_ALLOW_NO_FIRE_DATA", "1")
sys.path.insert(0, ".")
from ugv.roads import RoadNetwork  # noqa: E402
import ugv.tests.test_multi_vehicle as tm  # noqa: E402
from ugv.tests.test_multi_vehicle import FLEET_CFG, make_fleet  # noqa: E402
from ugv.approach import node_id_of  # noqa: E402

BUF_M = 12.0      # 최대 추정 반폭(3 차로 5.4 m) + 소방차 차체 반폭·회전 쓸림 여유 — 타일 경계 근처 판정용
STOP_M = 60.0     # 끝 지점 연장·정지 경로·대기 여유 (경로 끝 앞뒤)
T = json.load(open(tiles / "tiles.json", encoding="utf-8"))
TM = T["tile_m"]; OX, OY = T["origin_xy"]
have = set(T["tiles"].keys())
net = RoadNetwork(); tm.NET = net
cfg = {c["resource_id"]: c for c in FLEET_CFG}


def tile_of(x, y):
    return int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM))


def name(i, j):
    return f"T{i:02d}_{j:02d}"


def touch(x, y):
    s = set()
    for dx in (-BUF_M, 0, BUF_M):
        for dy in (-BUF_M, 0, BUF_M):
            s.add(tile_of(x + dx, y + dy))
    return s


def fleet(rid):
    f, _ = make_fleet(pathlib.Path(tempfile.mkdtemp()), [cfg[rid]]); return f.vehicles[rid]


res = {"tiles_dir": str(tiles), "tiles_json_sha1": hashlib.sha1((tiles / "tiles.json").read_bytes()).hexdigest(),
       "git_head": os.popen("git rev-parse HEAD").read().strip(), "git_dirty_ugv": os.popen("git status --porcelain --untracked-files=no -- ugv").read().strip(),
       "profiles_sha1": hashlib.sha1(pathlib.Path("ugv/profiles.py").read_bytes()).hexdigest(),
       "buf_m": BUF_M, "stop_m": STOP_M, "tile_m": TM, "origin_xy": [OX, OY], "routes": {}}
union_core = set()
for src, dst in [("A-ugv1", "B-ugv1"), ("B-ugv1", "A-ugv1"), ("A-fire1", "B-fire1"), ("B-fire1", "A-fire1")]:
    Vs, Vd = fleet(src), fleet(dst)
    body = {"task_id": "AB", "decision_id": "AB", "target_node": node_id_of(Vd.access)}
    ev = asyncio.run(Vs.evaluate(body))
    row = {"vehicle": Vs.profile.name, "planner": ev["verdict"], "eta_s": ev.get("eta_sec")}
    if ev["verdict"] == "ACCEPT":
        asyncio.run(Vs.execute(body))
        pts = [tuple(p) for p in Vs.plan.route.pts]
        core = set()
        for k, (x, y) in enumerate(pts):
            core |= touch(x, y)
            if k + 1 < len(pts):                      # 점 사이가 길면 보간 (타일 건너뜀 방지)
                x2, y2 = pts[k + 1]; n = int(math.dist((x, y), (x2, y2)) // 50)
                for q in range(1, n + 1):
                    core |= touch(x + (x2 - x) * q / (n + 1), y + (y2 - y) * q / (n + 1))
        for (x, y) in (pts[0], pts[-1]):              # 끝 여유
            for a in range(0, 360, 30):
                core.add(tile_of(x + STOP_M * math.cos(math.radians(a)), y + STOP_M * math.sin(math.radians(a))))
        row.update(route_m=round(sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)), 1), road_ids=list(Vs.plan.route.road_ids),
                   start_xy=[round(c, 1) for c in pts[0]], end_xy=[round(c, 1) for c in pts[-1]], core_tiles=sorted(name(*t) for t in core),
                   pts_sha1=hashlib.sha1(json.dumps([[round(a, 2), round(b, 2)] for a, b in pts]).encode()).hexdigest(), n_pts=len(pts))
        union_core |= core
    res["routes"][f"{src}->{dst}"] = row
    print(src, dst, row.get("planner"), row.get("route_m"), len(row.get("core_tiles", [])), flush=True)
nbr = set()
for (i, j) in union_core:
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            nbr.add((i + di, j + dj))
nbr -= union_core
allt = union_core | nbr
sizes = {}
for t in allt:
    d = tiles / name(*t)
    sizes[name(*t)] = sum(f.stat().st_size for f in d.iterdir()) if d.exists() else None
res.update(core_tiles=sorted(name(*t) for t in union_core), neighbor_tiles=sorted(name(*t) for t in nbr),
           missing_core=sorted(name(*t) for t in union_core if name(*t) not in have),
           missing_neighbor=sorted(name(*t) for t in nbr if name(*t) not in have),
           counts={"core": len(union_core), "neighbor": len(nbr), "total": len(allt)},
           area_km2={"core": len(union_core) * (TM / 1000) ** 2, "total": len(allt) * (TM / 1000) ** 2},
           disk_mb={"core": round(sum(sizes[name(*t)] or 0 for t in union_core) / 1e6, 1), "total": round(sum(v or 0 for v in sizes.values()) / 1e6, 1)},
           bbox_tiles={"i": [min(t[0] for t in allt), max(t[0] for t in allt)], "j": [min(t[1] for t in allt), max(t[1] for t in allt)]},
           memory_note="추정만 — 9 타일 월드 기동 직후 WSL used 841 MB vs 평지 774 MB (tz_startup.txt, gz+PX4 1대). 타일당 ≈ 7~8 MB 로 보면 "
                       "합집합 규모는 아래 total × 8 MB 수준이나 물리 heightfield·센서 갱신·장거리 RTF 는 대표 구간 실측으로만 판단 (Codex 4.6)")
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: res[k] for k in ("counts", "area_km2", "disk_mb", "bbox_tiles", "missing_core", "missing_neighbor")}, ensure_ascii=False))
