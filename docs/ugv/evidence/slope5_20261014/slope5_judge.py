"""경사 정지 반복 판정 (기준 logs/ugv/stage6/slope4/SLOPE4_criteria.md, Fable 미해결 3.3 + Codex 0130 P2/P4 규칙). ADAIR 루트에서:
  python logs/ugv/stage6/slope4/slope4_judge.py
입력: road_test 기록 ../ADAIR_wt_hook/logs/ugv/<tag>_*.json/.csv, slope_report (s4_slope_report.json), ULog 덤프 ulog_<tag>.json,
서버 park_events (logs/ugv/stage4/state_<tag>/park_events.jsonl), 래퍼 rc (logs/ugv/stage4/rc_<tag>.json).
상태: INVALID (래퍼) / UNCONFIRMED (자료 누락·공백) / PASS / FAIL. OFF 회차는 정지거리 기준값 기록만."""
import bisect
import glob
import json
import math
import os
from datetime import datetime
from pathlib import Path

R = Path(__file__).resolve().parents[4]
HK = R.parent / os.getenv("S4_TREE", "ADAIR_wt_hook")
O = R / "logs/ugv/stage6/slope5"
PFX = os.getenv("S4_PREFIX", "s5_")
GAP_MAX_S, POLL_S, LOCK_MARGIN_S = 0.3, 0.5, 0.1
OFF_MIN = {}
# 기존 OFF 참고 범위 (다른 서버 커밋): s0547 = chain_slope3 cs3off 3회 (9c49f69) 48.9~52.7 m, s3113 = chain_slope 3~4 % 중단 3회 (wt_fix) 40.6~43.2 m.
# Codex 0155 4.5: 코드 차이(9c49f69→899bb56: S6 경로·정지 관련)가 있어 두 사례 모두 현재 합본 OFF 를 새로 1회. 새 값이 참고 범위 ±5 m 안이면
# 기준 = min(참고 3회, 새 회차), 밖이면 OFF 2회 추가 전에는 ⑤ 미확인.
OFF_REF = {"s0547": (48.9, 52.7), "s3113": (40.6, 43.2)}
# v5: OFF 기준은 같은 계통(899bb56, 플래그 off 경로 동작 동일 — 341df20 은 플래그 off 에서 기록 필드만 추가) 의 s4r_off 2회 재사용
OFF_FIXED = {"s0547": 48.9, "s3113": 40.6}
YAW_JUMP_DEG = 5.0
SR = {}
try:
    SR = {r["tag"]: r for r in json.load(open(os.getenv("S4_SR", str(O / "s4_slope_report.json")), encoding="utf-8"))}
except Exception:  # noqa: BLE001
    pass


def gz_speed(rows, win=0.2):
    out, j = [], 0
    for i in range(len(rows)):
        while rows[i][0] - rows[j][0] > win:
            j += 1
        if j < i and rows[i][0] - rows[j][0] >= win * 0.5:
            out.append(((rows[i][0] + rows[j][0]) / 2, math.dist(rows[i][1:3], rows[j][1:3]) / (rows[i][0] - rows[j][0]), rows[i][4]))
    return out


def align(gz, ul, t_hint):
    ul = [p for p in ul if t_hint - 60 <= p[0] <= t_hint + 20 and p[1] > 0.5]
    if len(ul) < 20 or not gz:
        return None, None
    gt = [g[0] for g in gz]
    def rms(off):
        s, n = 0.0, 0
        for t, v in ul:
            i = bisect.bisect_left(gt, t - off)
            if 0 < i < len(gz):
                s += (gz[i][1] - v) ** 2; n += 1
        return math.sqrt(s / n) if n >= 0.8 * len(ul) else math.inf
    base = ul[0][0] - gz[0][0]
    best = min(((rms(base + d / 10), base + d / 10) for d in range(-3000, 3001, 5)), key=lambda x: x[0])
    if math.isinf(best[0]):
        return None, None
    fine = min(((rms(best[1] + d / 100), best[1] + d / 100) for d in range(-10, 11)), key=lambda x: x[0])
    return round(fine[1], 3), round(fine[0], 3)


def judge(tag):
    case = "s0547" if "s0547" in tag else "s3113"
    on = "_on_" in tag or os.getenv("S4_FORCE_ON") == "1"     # S4_FORCE_ON: 판정기 검증용 (E2 회차)
    rec = {"tag": tag, "case": case, "arm": "ON" if on else "OFF", "checks": {}}
    c = rec["checks"]
    try:
        w = json.load(open(R / f"logs/ugv/stage4/rc_{tag}.json", encoding="utf-8"))
    except Exception:  # noqa: BLE001
        w = {}
    marks = [m for m in ("contaminated", "invalid_evidence", "invalid_stop") if (R / f"logs/ugv/stage4/{tag}.{m}").exists()]
    valid = bool(w) and w.get("test_rc") == 0 and w.get("copy_logs_rc") == 0 and str(w.get("stop_post_rc")) == "0" and w.get("invalid_stop") is False and not marks
    rec["validity"] = {"rc": w, "markers": marks}
    js = sorted(glob.glob(str(HK / f"logs/ugv/{tag}_*.json")))
    if not js:
        rec["status"] = "NO_RECORD"; return rec
    d = json.load(open(js[-1], encoding="utf-8"))
    rows = []
    for ln in open(js[-1][:-5] + ".csv", encoding="utf-8").read().splitlines()[1:]:
        p = ln.split(",")
        rows.append((float(p[0]), float(p[1]), float(p[2]), float(p[4]), float(p[9])))      # sim_t, x, y, yaw, wall_t
    ev = d.get("events") or []
    sp = next((e for e in ev if e["event"] == "STOP_PATH"), None)
    rec["stop_path_event"] = sp
    s = SR.get(tag) or {}
    ab = s.get("abort") or {}
    rec["abort"] = ab; rec["phase_split_m"] = s.get("phase_split_m"); rec["judge3"] = s.get("judge3")
    dist = ab.get("stop_distance_m")
    need = (sp or {}).get("needed_m")
    rec["stop_distance_m"], rec["planned_needed_m"] = dist, need
    if not on:
        rec["status"] = "INVALID" if not valid else ("RECORD" if dist is not None else "UNCONFIRMED")
        return rec
    # ① F1: 업로드 전 상한 ACK + 정지 미션 첫 트리플릿 cruise = 상한 ±0.05
    cap = (sp or {}).get("speed_cap_first") or {}
    try:
        u = json.load(open(O / f"ulog_{tag}.json", encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        u = None; rec["ulog_error"] = repr(e)[:120]
    stop_m = (u or {}).get("stop_mission") or {}
    first_cr = None
    if u and stop_m:
        first_cr = next((v for t, v in u["triplet_cruise_changes"] if t >= stop_m["first_t"] - 0.1 and v > 0), None)
    rec["f1"] = {"cap": cap, "first_triplet_cruise": first_cr}
    c["1_f1_cap_applied"] = None if (u is None or first_cr is None or not cap) else (cap.get("ok") is True and abs(first_cr - cap["v"]) <= 0.05)
    # ② 명령 뒤 Gazebo 최고 ≤ 명령 시 + 0.5, 감속 시작 ≤ 1.0 s
    gz = gz_speed(rows)
    cmd_wall = datetime.fromisoformat(sp["timestamp"]).timestamp() if sp else None
    ps = s.get("phase_split_m") or {}
    if cmd_wall is not None and ps.get("cmd_to_decel_s") is not None:
        # sim_t ↔ wall: CSV 행마다 둘 다 있다 — 명령 wall 에 가장 가까운 행의 sim_t 를 명령 sim 시각으로
        k = min(range(len(rows)), key=lambda i: abs(rows[i][4] - cmd_wall))
        t_cmd = rows[k][0]
        v_cmd = next((v for t, v, _ in gz if t >= t_cmd), None)
        stop_t = next((t for t, v, _ in gz if t > t_cmd and v < 0.1), None)
        vmax = max((v for t, v, _ in gz if t_cmd <= t <= (stop_t or t_cmd + 30)), default=None)
        rec["cmd"] = {"sim_t": t_cmd, "wall_match_err_s": round(abs(rows[k][4] - cmd_wall), 3), "v_cmd_gz": v_cmd, "vmax_after": vmax,
                      "cmd_to_decel_s": ps.get("cmd_to_decel_s")}
        c["2_no_overspeed_decel_le_1s"] = (vmax is not None and v_cmd is not None and vmax <= v_cmd + 0.5 and ps["cmd_to_decel_s"] <= 1.0) \
            if abs(rows[k][4] - cmd_wall) <= 0.2 else None
    else:
        c["2_no_overspeed_decel_le_1s"] = None
    # 0) 공통 선행 조건 (Codex 0300 4절·Fable ⑤): 안전 사건 없음, start_item 0, run_id, 상한 의존 없음
    bad_ev = [e["event"] for e in ev if e["event"] in ("FAULT", "STOP_NOT_CONFIRMED", "STOP_CUT_DRIVE", "STOP_SLOW_FINISH_CUT")]
    rec["safety_events"] = bad_ev
    c["0a_no_fault_cut_notconfirmed"] = not bad_ev
    tm = (sp or {}).get("timing") or {}
    rec["timing"] = {k: tm.get(k) for k in ("t_enter", "t_upload_start", "upload_s", "start_item")}
    c["0b_start_item_0"] = None if tm.get("start_item") is None else tm["start_item"] == 0
    ramp = (sp or {}).get("stop_items_ramp") or {}
    rec["stop_items_ramp"] = ramp
    v_at = (sp or {}).get("speed_mps")
    c["0c_cap_not_crawl"] = None if (not cap or v_at is None) else cap.get("v", 0) >= v_at - 2.0
    sb = next((e for e in ev if e["event"] == "STOP_SUP_BEGIN"), None)
    scf = next((e for e in ev if e["event"] == "STOP_CONFIRMED"), None)
    rec["sup"] = {"begin": {k: sb.get(k) for k in ("t0", "t_allow_s", "allow_m", "reach_m", "v0", "lat_s")} if sb else None,
                  "confirmed": {k: scf.get(k) for k in ("time_s", "travel_m", "allow_m", "cut_drive")} if scf else None}
    c["0d_sup_margin_ge_3s"] = None if (not sb or not scf) else (scf["time_s"] <= sb["t_allow_s"] - 3.0 and scf["travel_m"] <= scf["allow_m"])
    # ③ a~e (정지 미션 finished 기준, E4 v2 와 같은 규칙)
    fin, dis = stop_m.get("finished_t"), (u or {}).get("disarm_t")
    sp0 = (u or {}).get("speed_sp_zero_after_finished_t")
    c["3a_px4_setpoint0"] = None if fin is None else (sp0 is not None and sp0 <= fin + 0.1)
    off, rms = align([(t, v) for t, v, _ in gz], (u or {}).get("speed_series") or [], fin or 0.0) if u else (None, None)
    pk = None
    try:
        lines = [json.loads(l) for l in open(R / f"logs/ugv/stage4/state_{tag}/park_events.jsonl", encoding="utf-8")]
        pk = ([x for x in lines if x.get("disarm_call") == "OK"] or [None])[-1]
    except Exception:  # noqa: BLE001
        pass
    rec["park_server"] = pk
    if off is not None and fin is not None and dis is not None:
        gu = [(t + off, v) for t, v, _ in gz]
        b = None
        for t, v in gu:
            if fin - 2.0 <= t <= fin + 1.5 and t < dis and v < 0.2 and all(vv < 0.2 for tt, vv in gu if t <= tt <= max(t, fin)):
                b = t; break
        last = b
        if b is not None:
            for t, v in gu:
                if t < b:
                    continue
                if v >= 0.2 or t > dis:
                    break
                last = t
        win = [t for t, _ in gu if (b or fin) - 1.0 <= t <= dis + 1.0]
        gap = max((y - x for x, y in zip(win, win[1:])), default=None)
        okg = gap is not None and gap <= GAP_MAX_S
        rec["e2_3"] = {"3b_t": b, "slow_until_t": last, "fin": fin, "disarm": dis, "gap": gap, "align": [off, rms],
                       "gz_stop_to_disarm_record": None if b is None else round(dis - b, 3)}
        c["3b"] = (b is not None and b <= fin + 1.5) if okg else None
        c["3c"] = (b is not None and last - b >= 1.0) if okg else None
    else:
        c["3b"] = c["3c"] = None
    cut = [e for e in ev if e["event"] == "STOP_CUT_DRIVE"]
    if pk:
        span = None if pk.get("still_since_mono") is None else pk["disarm_req_mono"] - pk["still_since_mono"]
        rec["run_id_match"] = pk.get("run_id") == tag              # Codex 0155 3절: 서버 park 기록이 이 회차 것인지
        c["3d_server_policy"] = None if not rec["run_id_match"] else (pk.get("reason") == "NORMAL_STILL" and span is not None
                                                                       and pk.get("after_s") <= span <= pk.get("after_s") + POLL_S + LOCK_MARGIN_S)
        c["3e_no_runaway_no_cutdrive"] = pk.get("reason") != "RUNAWAY_CAP" and not cut
    else:
        # park 기록이 없어도 구동 차단 이벤트가 있으면 ③e 는 거짓 (기준 문구 'STOP_CUT_DRIVE 없음' — 02:56 판정기 구현 수정, 결과 뒤)
        c["3d_server_policy"] = None
        c["3e_no_runaway_no_cutdrive"] = False if cut else None
    rec["stop_events"] = [{k: v for k, v in e.items() if k not in ("resource_id", "timestamp")} for e in ev
                          if e["event"] in ("STOP_NOT_CONFIRMED", "STOP_CUT_DRIVE", "FAULT", "STOP_CONFIRMED")]
    # ④ 차체 도로 안·30 s 이동 ≤ 0.1 m·yaw 급변 없음
    # 정지 유지 (중단 회차는 slope_report 에 hold 가 없다 → Gazebo 에서 직접): 명령 뒤 < 0.2 m/s 1 s 연속 확인 시각부터 30 s 동안
    # 최대 수평 이동·yaw 변화. 30 s 관측 부족이면 미확인
    j3, h, yaw_jump = s.get("judge3") or {}, {}, None
    t_cmd0 = (rec.get("cmd") or {}).get("sim_t")
    if t_cmd0 is not None:
        t_s = None
        for t, v, _ in gz:
            if t <= t_cmd0:
                continue
            if v < 0.2:
                t_s = t if t_s is None else t_s
                if t - t_s >= 1.0:
                    break
            else:
                t_s = None
        if t_s is not None:
            conf = t_s + 1.0
            hw = [r for r in rows if conf <= r[0] <= conf + 30]
            if hw and hw[-1][0] - conf >= 29.5:
                drift = max(math.dist(r[1:3], hw[0][1:3]) for r in hw)
                yaw_jump = max(abs(math.degrees(math.atan2(math.sin(r[3] - hw[0][3]), math.cos(r[3] - hw[0][3])))) for r in hw)
                h = {"confirm_sim_t": round(conf, 3), "drift_m": round(drift, 3), "observed_s": round(hw[-1][0] - conf, 1)}
            else:
                h = {"confirm_sim_t": round(conf, 3), "note": "30 s 관측 부족 — 미확인"}
    rec["hold"] = h
    rec["yaw_change_hold_deg"] = None if yaw_jump is None else round(yaw_jump, 2)
    c["4_inside_hold_yaw"] = None if (j3.get("inside") is None or h.get("drift_m") is None or yaw_jump is None) else \
        (j3["inside"] is True and h["drift_m"] <= 0.1 and yaw_jump <= YAW_JUMP_DEG)
    # ⑤ 정지거리 < 같은 사례 OFF 최소, 그리고 ≤ 계획 정지 경로 + 1.0 m
    offm = OFF_MIN.get(case)
    rec["off_min_m"] = offm
    c["5_stop_distance"] = None if (dist is None or need is None or offm is None or dist < need - 4.0) else (dist < offm and dist <= need + 1.0)
    rec["limits"] = ["seq 경유점 누락 미확인", "Gazebo 속도 0.2 s 창", "정렬 rms 는 시각 불확실성 아님"]
    if not valid:
        rec["status"] = "INVALID"
    elif any(v is False for v in c.values()):       # 확정된 거짓이 있으면 실패 (미확인 항목이 남아도) — 02:57 수정
        rec["status"] = "FAIL"
    elif any(v is None for v in c.values()):
        rec["status"] = "UNCONFIRMED"
    else:
        rec["status"] = "PASS"
    return rec


tags = sorted({Path(p).name.rsplit("_", 2)[0] for p in glob.glob(str(HK / f"logs/ugv/{PFX}*_*.json"))})
offs = [judge(t) for t in tags if "_off_" in t]
OFF_MIN.update(OFF_FIXED); OFF_MIN["note"] = "s4r_off (899bb56) 새 OFF 1회씩 + 참고 범위로 정한 기준 재사용 (SLOPE5_criteria)"
for case, (lo, hi) in ({} if True else OFF_REF).items():
    new = [r["stop_distance_m"] for r in offs if r["case"] == case and r.get("stop_distance_m") is not None and r["status"] == "RECORD"]
    if not new:
        OFF_MIN[case + "_note"] = "현재 합본 OFF 없음 — ⑤ 미확인"; continue
    if len(new) >= 3:
        OFF_MIN[case] = min(new); OFF_MIN[case + "_note"] = f"현재 합본 OFF {len(new)}회 최소"
    elif all(lo - 5 <= x <= hi + 5 for x in new):
        OFF_MIN[case] = min([lo] + new); OFF_MIN[case + "_note"] = f"새 OFF {new} 가 참고 {lo}~{hi} ±5 m 안 → min(참고, 새)"
    else:
        OFF_MIN[case + "_note"] = f"새 OFF {new} 가 참고 {lo}~{hi} ±5 m 밖 → OFF 2회 추가 필요 (Fable 3.2), ⑤ 미확인"
res = offs + [judge(t) for t in tags if "_on_" in t or os.getenv("S4_FORCE_ON") == "1"]
json.dump({"off_min": OFF_MIN, "runs": res}, open(O / f"{PFX}judge.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("OFF_MIN", OFF_MIN)
for r in res:
    print(r["tag"], r["status"], r.get("checks"), "dist", r.get("stop_distance_m"), "need", r.get("planned_needed_m"), "f1", r.get("f1"))
