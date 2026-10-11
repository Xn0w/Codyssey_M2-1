"""시작 항목 기록(start_item_watch.py jsonl) ↔ UGV 서버 로그의 MAVSDK 'Current: N, total: M' (UTC 시각) 대응.
MAVSDK 로그 시각은 현지 시각 12 시간제 (18:33 → 06:33) — 현지 시각 mod 12 h 로 맞춘다.
미션마다: 송신 시각, 지정 시작 항목, PX4 가 처음 보고한 진행 항목들(업로드 직후 0 → 지정 항목 → 이후 순서), 되돌기(항목 번호 감소) 여부.
  python integration/px4_live/match_start_items.py <start_items.jsonl> <ugv.log>
"""
import json
import re
import sys

PAT = re.compile(r"\[(\d\d):(\d\d):(\d\d)\|Debug\] Current: (\d+), total: (\d+)")


def sec(h, m, s):
    return int(h) * 3600 + int(m) * 60 + int(s)


def main(jl, log):
    recs = [json.loads(x) for x in open(jl, encoding="utf-8") if x.strip()]
    cur = []
    for line in open(log, encoding="utf-8", errors="replace"):
        m = PAT.search(line)
        if m:
            cur.append((sec(*m.group(1, 2, 3)) % 43200, int(m.group(4)), int(m.group(5))))
    out = []
    for i, r in enumerate(recs):
        t0 = sec(*r["mission_sent_at"].split(".")[0].split(":")) % 43200
        t1 = sec(*recs[i + 1]["mission_sent_at"].split(".")[0].split(":")) % 43200 if i + 1 < len(recs) else 10 ** 9
        total = r["n_items"] + 0                         # 서버 미션 항목 수 (PX4 total 은 같거나 +선행 처리)
        seq = [(t, c, tot) for t, c, tot in cur if t0 - 2 <= t < t1 and abs(tot - total) <= 1]
        items = []
        for _, c, _ in seq:
            if not items or items[-1] != c:
                items.append(c)
        back = any(b < a for a, b in zip(items[1:], items[2:]))   # 첫 0 (업로드 직후) 뒤 번호 감소 = 되돌기
        first_exec = items[1] if len(items) > 1 and items[0] == 0 else (items[0] if items else None)
        o = {**{k: r.get(k) for k in ("mission_sent_at", "mission_sent_utc", "task_id", "n_items", "start_item",
                                       "dist_here_to_selected_m", "selected_ahead_of_start", "route_segments_passing_start")},
             "mavsdk_current_seq_head": items[:6], "mavsdk_first_after_upload": first_exec, "mavsdk_items_seen": len(items),
             "went_back": back}
        out.append(o)
        print(json.dumps(o, ensure_ascii=False))
    return out


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
