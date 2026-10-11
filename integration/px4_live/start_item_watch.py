"""UGV 미션 시작 항목 기록기 (읽기 전용, GET /ugv/{id}/route 의 last_sent_mission). 통합 실행 동안 따로 띄운다.
새 미션(wall 바뀜)마다: 계획 출발점 here, 지정 시작 항목 start_item (없으면 0 = 미지정), 그 항목까지 거리, 차 앞 여부(경로 진행상 출발점보다 뒤),
경로상 구간 번호, 같은 자리를 다시 지나는 구간 수 (되돌아오는 경로 여부), 업로드 상한 start_reach_m.
  python integration/px4_live/start_item_watch.py <출력 jsonl> [--rid A-ugv1] [--minutes 40]
"""
import argparse
import json
import math
import time

import httpx


def seg_hits(pts, p, tol=3.0):
    """p 에서 tol m 안을 지나는 미션 선분 번호들 (같은 자리 재통과 확인)."""
    out = []
    for k, (a, b) in enumerate(zip(pts, pts[1:])):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        if math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy) <= tol:
            out.append(k)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--rid", default="A-ugv1")
    ap.add_argument("--url", default="http://127.0.0.1:8100")
    ap.add_argument("--minutes", type=float, default=40)
    a = ap.parse_args()
    c = httpx.Client(base_url=a.url, timeout=10, headers={"X-ADAIR-Monitor": "1"})
    seen = None
    end = time.time() + a.minutes * 60
    with open(a.out, "a", encoding="utf-8") as f:
        while time.time() < end:
            try:
                r = c.get(f"/ugv/{a.rid}/route").json()
            except Exception:  # noqa: BLE001  (서버 기동 전·종료 뒤)
                time.sleep(2)
                continue
            ls = r.get("last_sent_mission") or {}
            if ls.get("wall") and ls.get("wall") != seen:
                time.sleep(1.5)                       # 업로드·시작 항목 지정이 끝난 뒤 값
                try:
                    ls = c.get(f"/ugv/{a.rid}/route").json().get("last_sent_mission") or ls
                except Exception:  # noqa: BLE001
                    pass
                seen = ls.get("wall")
                here = ls.get("here")
                items = ls.get("items") or []
                k0 = int(ls.get("start_item") or 0)
                pts = [tuple(here)] + [tuple(it[:2]) for it in items] if here else [tuple(it[:2]) for it in items]
                rec = {"mission_sent_at": time.strftime("%H:%M:%S", time.localtime(seen)) + f".{int((seen % 1) * 1000):03d}",
                       "mission_sent_utc": time.strftime("%H:%M:%S", time.gmtime(seen)),   # MAVSDK 로그 시각과 맞춤 (UTC)
                       "recorded_at": time.strftime("%H:%M:%S"), "wall": seen,
                       "task_id": r.get("task_id"), "n_items": len(items), "start_item": k0,
                       "start_item_set": "start_item" in ls, "start_reach_m": ls.get("start_reach_m"),
                       "start_item_error": ls.get("start_item_error")}
                if here and items:
                    sel = items[k0][:2]
                    rec["dist_here_to_selected_m"] = round(math.dist(here, sel), 1)
                    along = sum(math.dist(pts[i], pts[i + 1]) for i in range(k0 + 1))   # here → 선택 항목 경로 거리
                    rec["selected_along_route_m"] = round(along, 1)
                    rec["selected_ahead_of_start"] = along > 0.0
                    hits = seg_hits(pts, tuple(here))
                    rec["route_segments_passing_start"] = hits          # [0] 이면 출발 자리를 한 번만 지남, 더 있으면 되돌아오는 경로
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                print(json.dumps(rec, ensure_ascii=False), flush=True)
            time.sleep(3.0)


if __name__ == "__main__":
    main()
