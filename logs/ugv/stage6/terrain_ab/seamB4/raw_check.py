"""점별 원본 접촉 분석 (WSL python3, Codex 1045): gz_detail_seam_v3 의 <TAG>_raw.jsonl → 바퀴별 (정착 2 s 뒤) 점 수, 접촉 상대, 엔진 body1 이 바퀴인지 (force 부호 결정),
바퀴에 작용하는 점별 힘 F_w (f1.z > 0 이면 f1, 아니면 f2 — 정지 지지 조건으로 엔진 body 순서 추론), 법선 n_w (바퀴 쪽을 향하도록 n·F_w ≥ 0 이면 그대로 아니면 −n), 점별 법선 기울기 (수직과 각도)·축 방향 (월드 x) 성분,
점별 ft/fn = |F_w − (F_w·n̂)n̂| / (F_w·n̂), depth. 출력 = 중앙값·최대. 판정 없음 (기록·해석용)."""
import json, math, sys, statistics as st
from pathlib import Path
O = Path(sys.argv[1]); tag = sys.argv[2]
L = [json.loads(l) for l in open(O / f"{tag}_raw.jsonl") if l.strip()]
t0 = L[0]["sim_t"]; L = [x for x in L if x["sim_t"] >= t0 + 2.0]
res = {"tag": tag, "n_samples": len(L), "wheels": {}}
for w in ("wheel_front_left", "wheel_front_right", "wheel_rear_left", "wheel_rear_right"):
    tilt, ax, rat, dep, npts, others, b1w = [], [], [], [], [], set(), set()
    for x in L:
        r = (x["wheels"] or {}).get(w)
        if not r: continue
        npts.append(len(r["pts"]))
        for p in r["pts"]:
            others.add(p.get("c2")); 
            if "f1" not in p or "n" not in p: continue
            # gz-sim 은 JointWrench body 이름을 채우지 않고 메시지 c1 = 센서 쪽 (엔진 순서 아님) → 엔진 body1 판별은 정지 지지 조건으로 추론:
            # 바퀴에 작용하는 지지력은 +z → f1.z > 0 이면 엔진 body1 = 바퀴 (추론, 기록)
            wheel_is_b1 = p["f1"][2] > 0
            b1w.add(wheel_is_b1)
            F = p["f1"] if wheel_is_b1 else p["f2"]; n = p["n"]; nn = math.sqrt(sum(v * v for v in n)) or 1.0; n = [v / nn for v in n]
            fn = sum(F[i] * n[i] for i in range(3))
            if fn < 0: n = [-v for v in n]; fn = -fn
            ft = math.sqrt(max(0.0, sum(F[i] ** 2 for i in range(3)) - fn * fn))
            tilt.append(math.degrees(math.acos(max(-1, min(1, n[2]))))); ax.append(n[0]); rat.append(ft / fn if fn > 1e-6 else float("nan")); dep.append(p.get("d", float("nan")))
    q = lambda v: None if not v else {"median": round(st.median(v), 4), "max": round(max(v), 4), "min": round(min(v), 4)}
    res["wheels"][w] = {"pts_per_msg": q(npts), "others": sorted(o for o in others if o), "wheel_is_engine_body1": sorted(b1w), "normal_tilt_deg": q(tilt), "normal_x": q(ax), "ft_fn_point": q([r for r in rat if r == r]), "depth": q([d for d in dep if d == d])}
json.dump(res, open(O / f"rawcheck_{tag}.json", "w"), ensure_ascii=False, indent=1)
for w, v in res["wheels"].items(): print(tag, w, json.dumps(v, ensure_ascii=False))
