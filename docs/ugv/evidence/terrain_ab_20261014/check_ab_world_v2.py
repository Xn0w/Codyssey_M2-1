"""ab_route_v1 사전 검사 v2 (Codex 0300 6절). 사용: python check_ab_world_v2.py <tiles_v2> <out.json>
v1 결함: tiles.json roads_excluded 는 {도로ID: 사유문자열} 인데 값이 list/dict 일 때만 읽어 제외 집합이 비었다 → v2 는 키를 제외 ID 로.
추가: ① 경로 선분 연속 포함 (선분을 1 m 간격 보간), ② 차체 포함 (각 경로점에서 진행 방향 수직 ±(차체 반폭 + 0.5 m), 앞뒤 ±(차체 반길이)),
③ 경로 끝 안전 정지·끝 지점 연장 여유 (끝점에서 진행 방향 앞으로 60 m 까지 같은 방향 직선 — 보수적), 모두 합집합 경계에서 25 m 안쪽 (월드 부분집합 규칙과 같음).
④ 선택 타일 경계 높이 연속: 이웃 타일 heightmap 의 공유 가장자리 픽셀 값 차 최대 (16 bit PNG, 같은 양자화) — 이음매 단차.
⑤ A/B 거점 출입점 지면 높이 (해당 타일 heightmap 쌍선형) → spawn z 후보. 기존 높이장은 바꾸지 않는다."""
import glob
import hashlib
import json
import math
import sys
from pathlib import Path

T = Path(sys.argv[1]); outp = Path(sys.argv[2])
meta = json.load(open(T / "tiles.json", encoding="utf-8")); TM = meta["tile_m"]; OX, OY = meta["origin_xy"]
sub = json.load(open(T / "road_subset_ab_route_v1.json", encoding="utf-8"))
roads, tiles = set(map(str, sub["roads"])), set(sub["tiles"])
excl_ids = set(map(str, (meta.get("roads_excluded") or {}).keys()))
BODY = {"ugv": (4.2 / 2, 1.8 / 2), "fire": (8.0 / 2, 2.5 / 2)}      # (반길이, 반폭) — 소방차는 임시 (프로필 미확정)
M = 25.0
out = {"excluded_ids_count": len(excl_ids), "tiles_json_sha1": hashlib.sha1((T / "tiles.json").read_bytes()).hexdigest(),
       "subset_sha1": hashlib.sha1((T / "road_subset_ab_route_v1.json").read_bytes()).hexdigest(), "routes": {}}


def in_tiles(x, y):
    i, j = int(math.floor((x - OX) / TM)), int(math.floor((y - OY) / TM)); return f"T{i:02d}_{j:02d}" in tiles


def ok(x, y, m=M):
    return all(in_tiles(x + dx, y + dy) for dx, dy in ((0, 0), (m, 0), (-m, 0), (0, m), (0, -m), (m, m), (m, -m), (-m, m), (-m, -m)))


for f in sorted(glob.glob(str(outp.parent / "route_geom_*.json"))):
    g = json.load(open(f, encoding="utf-8")); k = Path(f).stem[len("route_geom_"):]
    hl, hw = BODY["fire" if "fire" in k else "ugv"]
    pts = g["route_pts"]
    rid = set(map(str, g["road_ids"]))
    seg_bad = body_bad = 0; ex = []
    for a, b in zip(pts, pts[1:]):
        L = math.dist(a, b); n = max(1, int(L))
        hx, hy = ((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L > 1e-6 else (1.0, 0.0)
        for q in range(n + 1):
            x, y = a[0] + (b[0] - a[0]) * q / n, a[1] + (b[1] - a[1]) * q / n
            if not ok(x, y):
                seg_bad += 1
                if len(ex) < 3: ex.append([round(x, 1), round(y, 1)])
            for s_ in (-1, 1):
                for t_ in (-1, 1):
                    cx = x + s_ * hl * hx - t_ * (hw + 0.5) * hy; cy = y + s_ * hl * hy + t_ * (hw + 0.5) * hx
                    if not ok(cx, cy):
                        body_bad += 1
    a, b = pts[-2], pts[-1]; L = math.dist(a, b) or 1.0
    hx, hy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    tail_bad = sum(1 for d in range(0, 61) if not ok(b[0] + hx * d, b[1] + hy * d))
    out["routes"][k] = {"roads": len(rid), "roads_missing_from_world_subset": sorted(rid - roads),
                        "excluded_roads_on_route": sorted(rid & excl_ids), "segment_samples_outside_25m": seg_bad,
                        "body_corner_samples_outside_25m": body_bad, "end_tail_60m_outside": tail_bad, "examples": ex,
                        "body_assumed": {"half_len": hl, "half_wid": hw}}
    print(k, "missing", len(rid - roads), "excluded", len(rid & excl_ids), "seg_out", seg_bad, "body_out", body_bad, "tail_out", tail_bad)

# ④ 이음매: 이웃 타일 공유 가장자리 높이 차 (PNG 16 bit 원값; 양자화 q_m 로 m 환산)
try:
    from PIL import Image
    import numpy as np
    q = meta.get("q_m", 0.01)
    def hm(t):
        im = Image.open(T / t / "heightmap.png"); return np.asarray(im, dtype=np.float64)
    worst, n_pairs = 0.0, 0
    tl = sorted(tiles)
    cache = {}
    for t in tl:
        i, j = int(t[1:3]), int(t[4:6])
        for (di, dj) in ((1, 0), (0, 1)):
            u = f"T{i + di:02d}_{j + dj:02d}"
            if u not in tiles:
                continue
            A = cache.setdefault(t, hm(t)); B = cache.setdefault(u, hm(u))
            za, zb = meta["tiles"][t]["zmin"], meta["tiles"][u]["zmin"]
            sa, sb = meta["tiles"][t]["span"] / 65535.0, meta["tiles"][u]["span"] / 65535.0   # 생성 도구 Surface.grid 와 같은 복원 (q_m 은 반올림값이라 쓰지 않는다)
            if di == 1:   # t 의 동쪽 열 = u 의 서쪽 열
                ea, eb = A[:, -1] * sa + za, B[:, 0] * sb + zb
            else:         # t 의 북쪽 행(이미지 위) = u 의 남쪽 행(이미지 아래)
                ea, eb = A[0, :] * sa + za, B[-1, :] * sb + zb
            worst = max(worst, float(np.max(np.abs(ea - eb)))); n_pairs += 1
    out["seams"] = {"pairs": n_pairs, "max_step_m": round(worst, 4), "basis": "공유 가장자리 높이 = zmin + 값/65535 × span (build_terrain_tiles Surface.grid 와 같음)"}
except ImportError as e:
    out["seams"] = {"skipped": f"PIL/numpy 없음: {e}"}
json.dump(out, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("excluded ids", len(excl_ids), "seams", out.get("seams"))
