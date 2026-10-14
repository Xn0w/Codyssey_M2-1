import json, sys
for f in sys.argv[1:]:
    d = json.load(open(f, encoding="utf-8"))
    a = d.get("analysis") or {}
    print("==", f.split("\\")[-1].split("/")[-1])
    for k, v in (a.get("vehicles") or {}).items():
        print(f"  {k:8} 거리 {v.get('distance_m')} 최고 {v.get('max_speed_kmh')} km/h 끝속도 {v.get('final_speed_mps')} 이탈 {v.get('offroad_max_m')}({v.get('offroad_events')}) 전복 {v.get('rollover')}")
    for k, v in (a.get("pairs") or {}).items():
        print(f"  {k}: 간격 {v.get('min_center_gap_minus_half_lengths_m')} 겹침 {v.get('body_overlap_samples')}")
    for k, v in (a.get("tasks") or d.get("tasks") or {}).items():
        print("  task", k, v)
    for k in ("link_cut_t", "faults", "special_plan"):
        if k in d:
            print("  ", k, json.dumps(d[k], ensure_ascii=False)[:300])
    ev = d.get("events") or {}
    for rid, es in ev.items():
        names = [e.get("event") or e.get("type") for e in es]
        print("  ev", rid, names[-25:])
