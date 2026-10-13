"""E4 회차 판정 v3 (2026-10-14, 최종 500 Hz 후보 정상 도착 회귀 — Codex 0650/0723) = v2 + 0e 500 Hz 적용 + 0h 정지 경로(STOP_PATH) 없음 + FAIL 이 UNCONFIRMED 보다 우선.
이하 v2 설명.
E4 회차 판정 v2 (기준 logs/ugv/stage6/e4/E4_criteria_v2.md, Codex 0130 P1~P4 반영, 새 회차 전 고정).
v1(e4_judge.py) 과 차이: 래퍼 유효성 게이트, 서버 park 기록(park_events.jsonl)으로 정책 타이밍·실제 분기, ③b 사전 정지 연속성,
표본 공백·자료 누락 = UNCONFIRMED (PASS 아님), ULog 덤프 v2 의 speed_sp_zero.
 ADAIR 루트에서: python logs/ugv/stage6/e4/e4_judge.py
입력: road_test 기록 ../ADAIR_wt_hook/logs/ugv/<tag>_*.json/.csv, ULog 덤프 logs/ugv/stage6/e4/ulog_<tag>.json (e4_ulog_dump.py, WSL),
slope_report e4_slope_report.json (judge3·hold v2), 래퍼 rc logs/ugv/stage4/rc_<tag>.json.
Gazebo↔ULog 시각 정렬: Gazebo 속도(위치 차분, sim_t) 와 ULog 지역 위치 속도의 rms 최소 오프셋 (E2 방식). rms 기록."""
import glob
import json
import math
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[5]          # ADAIR (terrain_ab/envB 는 한 단계 깊음)
import os
HK = R.parent / os.getenv("E4_TREE", "ADAIR_wt_hook")      # 검증용: E4_TREE=ADAIR_wt_integ_next E4_PREFIX=e3
PFX = os.getenv("E4_PREFIX", "tb1_")
sys.path.insert(0, str(HK))
from ugv.geo import GZ_FRAME  # noqa: E402

O = R / "logs/ugv/stage6/terrain_ab/envB"
CASES = {"segB": ("acc3", None),          # (단계 B) 실제 지형 저속 선별 — 기존 E3 경계 값 대조 없음
         "acc3_s1096": ("acc3", -2.48), "raoff_s1096": ("raoff", -2.45), "acc3_s3113": ("acc3", None),
         "e3acc": ("acc3", -2.48), "e3base": ("raoff", -2.45)}       # e3* = 판정기 검증용 (연장 없음이라 1·2 는 실패가 정상)
GAP_MAX_S = 0.3        # ③ 판정 구간 Gazebo 표본 최대 공백 — 넘으면 미확인
POLL_S, LOCK_MARGIN_S = 0.5, 0.1
SR = {}
try:
    SR = {r["tag"]: r for r in json.load(open(O / os.getenv("E4_SR", "e4_slope_report.json"), encoding="utf-8"))}
except Exception:  # noqa: BLE001
    pass


def gz_speed(rows, win=0.2):
    """0.2 s 창 위치 차분 (CSV 좌표 0.01 m 반올림 — 표본 간 차분은 ±0.2 m/s 잡음, slope_report 와 같은 창)."""
    out, j = [], 0
    for i in range(len(rows)):
        while rows[i][0] - rows[j][0] > win:
            j += 1
        if j < i and rows[i][0] - rows[j][0] >= win * 0.5:
            out.append(((rows[i][0] + rows[j][0]) / 2, math.dist(rows[i][1:3], rows[j][1:3]) / (rows[i][0] - rows[j][0])))
    return out


def align(gz, ul, t_hint):
    """오프셋 off: ULog t ≈ gz sim_t + off. finished 근처 ±60 s 창에서 rms 최소."""
    # 움직이는 표본만 (> 0.5 m/s) — 정지 구간끼리 맞으면 rms 가 작아도 엉뚱한 정렬이 된다 (E3 검증에서 발견). 겹침 80 % 미만 오프셋은 버림
    ul = [p for p in ul if t_hint - 60 <= p[0] <= t_hint + 20 and p[1] > 0.5]
    if len(ul) < 20 or not gz:
        return None, None
    import bisect
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



def c7_ops(b, run_end, dis, gz_u):
    """(ops, Codex 0755/0806, 도착 회차 실행 전) 7c: 7b 뒤 < 0.2 연속 ≥ 1.0 s 가 disarm 전에 끝남.
    True = 관측 연속 ≥ 1.0 s. False = disarm 전에 다시 ≥ 0.2 (실제 끊김) 또는 b 없음.
    None (UNCONFIRMED, 증거 절단) = disarm 직전 마지막 표본까지 < 0.2 가 이어졌는데 운영 park 1.0 s 로 창이 1.0 s 에 못 미침."""
    if b is None or run_end is None:
        return False
    if run_end - b >= 1.0:
        return True
    broke = any(v >= 0.2 for t, v in gz_u if run_end < t < dis)
    return False if broke else None

def judge(tag):
    kind = next(v for k, v in CASES.items() if k in tag)
    rec = {"tag": tag, "kind": kind[0], "checks": {}}
    c = rec["checks"]
    try:
        rec["wrapper_rc"] = json.load(open(R / f"logs/ugv/stage4/rc_{tag}.json", encoding="utf-8"))
    except Exception:  # noqa: BLE001
        rec["wrapper_rc"] = None
    js = sorted(glob.glob(str(HK / f"logs/ugv/{tag}_*.json")))
    if not js:
        rec["status"] = "NO_RECORD"; return rec
    w = rec["wrapper_rc"] or {}
    marks = [m for m in ("contaminated", "invalid_evidence", "invalid_stop") if (R / f"logs/ugv/stage4/{tag}.{m}").exists()]
    rec["validity"] = {"rc_file": bool(w), "test_rc": w.get("test_rc"), "copy_logs_rc": w.get("copy_logs_rc"),
                       "stop_post_rc": w.get("stop_post_rc"), "invalid_stop": w.get("invalid_stop"), "markers": marks}
    valid = bool(w) and w.get("test_rc") == 0 and w.get("copy_logs_rc") == 0 and str(w.get("stop_post_rc")) == "0" \
        and w.get("invalid_stop") is False and not marks
    d = json.load(open(js[-1], encoding="utf-8"))
    rows = []
    for ln in open(js[-1][:-5] + ".csv", encoding="utf-8").read().splitlines()[1:]:
        p = ln.split(",")
        rows.append((float(p[0]), float(p[1]), float(p[2])))
    ev = d.get("events") or []
    ext = [e for e in ev if e["event"] in ("END_EXTENSION", "END_EXTENSION_SKIPPED")]
    rec["end_extension"] = ext[-1] if ext else None
    dev = ((d.get("state") or {}).get("driver_evidence")) or {}
    rec["driver_evidence"] = dev
    es, pp = dev.get("end_stop") or {}, dev.get("park_policy") or {}
    if kind[0] == "acc3":
        c["1_evidence"] = bool(ext and ext[-1]["event"] == "END_EXTENSION" and abs((ext[-1].get("offset_m") or 0) - 3.0) < 1e-6
                               and es.get("RA_ACC_RAD_MAX") == 3.0 and pp.get("after_s") == 1.0 and pp.get("test_hook") is False)   # (ops) 운영 park 1.0
    else:
        c["1_evidence"] = bool(ext and ext[-1]["event"] == "END_EXTENSION_SKIPPED" and str(ext[-1].get("reason", "")).startswith("OFFSET_0")
                               and (es.get("RA_ACC_RAD_MAX") or 0) < (es.get("NAV_ACC_RAD") or 0) and pp.get("after_s") == 1.0 and pp.get("test_hook") is False)
    pt = (((d.get("final") or {}).get("approach") or {}).get("point")) or {}
    arr = [e for e in ev if e["event"] == "ARRIVED"]
    rec["arrived_to_dest_m"] = arr[-1].get("to_dest_m") if arr else None
    c["8_arrived_to_dest_le_1m"] = bool(arr and arr[-1].get("to_dest_m") is not None and arr[-1]["to_dest_m"] <= 1.0)
    hold = (SR.get(tag) or {}).get("hold") or {}
    # 최종 정지 위치: 정지 확인 시각(hold.confirm_sim_t) 의 Gazebo 위치, 없으면 마지막 표본
    t_stop = hold.get("confirm_sim_t")
    stop = min(rows, key=lambda r: abs(r[0] - t_stop)) if t_stop else rows[-1]
    if pt.get("lat") is not None:
        dx, dy = GZ_FRAME.to_xy(pt["lat"], pt["lon"])
        rec["final_stop_to_service_dest_m"] = round(math.dist(stop[1:3], (dx, dy)), 3)
        c["2_service_dest_le_1m"] = rec["final_stop_to_service_dest_m"] <= 1.0
    else:
        c["2_service_dest_le_1m"] = False
    j3 = (SR.get(tag) or {}).get("judge3") or {}
    rec["judge3"] = j3
    c["4_judge3"] = bool(j3.get("final_pass")) and (kind[1] is None or (j3.get("outside_max_m") is not None and abs(j3["outside_max_m"] - kind[1]) <= 0.3))
    rec["hold"] = hold
    c["5_hold_le_0.1m_30s"] = hold.get("drift_m") is not None and hold["drift_m"] <= 0.1
    try:
        u = json.load(open(O / f"ulog_v2_{tag}.json", encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        rec["ulog_error"] = repr(e); rec["status"] = "INCOMPLETE"; return rec
    rec["ulog"] = {k: u.get(k) for k in ("params", "seq_total", "seq_reached", "finished_t", "speed_sp_zero_after_finished_t", "disarm_t", "cmd400_t", "acceptance_radius_values")}
    sq = u["seq_reached"]
    pos = [s for s in sq if s >= 0]
    missing = sorted(set(range(min(pos), max(pos) + 1)) - set(pos)) if pos else []
    rec["seq_missing"] = missing
    # ULog 의 mission_result 는 기록 주기로 솎여 중간 seq 가 빠져 보인다 (E3 두 회차 모두 홀수만) → 판정: 마지막 도달 = seq_total−1, 되돌아감 없음. 빠짐 목록은 기록
    c["3_seq_complete_monotonic"] = bool(pos) and max(pos) == u["seq_total"] - 1 and all(x <= y for x, y in zip(pos, pos[1:]))
    fin, sp0, dis = u.get("finished_t"), u.get("speed_sp_zero_after_finished_t"), u.get("disarm_t")
    if kind[0] == "acc3":
        c["6_px4_self_stop"] = fin is not None and sp0 is not None and sp0 <= fin + 0.1
    off, rms = align(gz_speed(rows), u["speed_series"], fin or 0.0)
    rec["align"] = {"offset_s": off, "rms_mps": rms}
    after = pp.get("after_s") or 1.0
    if off is not None and fin is not None and dis is not None:
        gz_u = [(r_t + off, v) for r_t, v in gz_speed(rows)]          # ULog 시각으로
        # ③b: finished + 1.5 s 안 · disarm 전 < 0.2 m/s 도달 / ③c: 그 뒤 < 0.2 연속 ≥ 1.0 s 가 disarm 전에 끝남
        # ③b v2: [fin−2, fin+1.5] 에서 < 0.2 가 되는 첫 시각 t, 단 t 가 finished 이전이면 t~finished 내내 < 0.2 (사전 정지 연속)
        b = None
        for t, v in gz_u:
            if fin - 2.0 <= t <= fin + 1.5 and t < dis and v < 0.2 and all(vv < 0.2 for tt, vv in gz_u if t <= tt <= max(t, fin)):
                b = t; break
        win = [t for t, _ in gz_u if (b or fin) - 1.0 <= t <= dis + 1.0]
        gap = max((y - x for x, y in zip(win, win[1:])), default=None)
        run_end, last = None, b
        if b is not None:
            for t, v in gz_u:
                if t < b:
                    continue
                if v >= 0.2 or t > dis:
                    break
                last = t
            run_end = last
        rec["e2_3"] = {"3b_t": b, "slow_run_until_t": run_end, "disarm_t": dis, "after_s": after,
                       "gz_stop_to_disarm_s_record_only": None if b is None else round(dis - b, 3),
                       "gz_max_gap_s": None if gap is None else round(gap, 3), "align_offset_s": off, "align_rms_mps": rms,
                       "align_note": "rms 는 속도 일치도이지 시각 정렬 불확실성이 아니다 (Codex 0130 P2)"}
        ok_gap = gap is not None and gap <= GAP_MAX_S
        # 서버 정책 (같은 서버 monotonic): park_events.jsonl 의 이 회차 마지막 실제 disarm 기록
        pk, pk_err = None, None
        try:
            ev_lines = [json.loads(l) for l in open(R / f"logs/ugv/stage4/state_{tag}/park_events.jsonl", encoding="utf-8")]
            done = [x for x in ev_lines if x.get("disarm_call") == "OK"]
            pk = done[-1] if done else None
        except Exception as e:  # noqa: BLE001
            pk_err = repr(e)[:120]
        rec["park_server"] = pk or {"missing": pk_err or "disarm 기록 없음"}
        cut = [e for e in ev if e["event"] == "STOP_CUT_DRIVE"]
        if pk:
            span = None if pk.get("still_since_mono") is None else pk["disarm_req_mono"] - pk["still_since_mono"]
            rec["park_server"]["still_to_disarm_req_s"] = None if span is None else round(span, 3)
            rec["park_server"]["lock_wait_s"] = round(pk["lock_mono"] - pk["decide_mono"], 3)
            d7 = pk.get("reason") == "NORMAL_STILL" and pk.get("after_s") == after and span is not None \
                and after <= span <= after + POLL_S + LOCK_MARGIN_S
            e7 = pk.get("reason") != "RUNAWAY_CAP" and not cut
        else:
            d7 = e7 = None                                         # 자료 없음 = 미확인
        e2 = {"7b": (b is not None) if ok_gap else None,
              "7c": c7_ops(b, run_end, dis, gz_u) if ok_gap else None,
              "7d_server_policy": d7, "7e_no_runaway_no_cutdrive": e7}
    else:
        e2 = {"7b": None, "7c": None, "7d_server_policy": None, "7e_no_runaway_no_cutdrive": None}
    if kind[0] == "acc3":          # ③ 은 PX4 끝 지점 자체 정지 차에만 정의 (E2). RA −1 차는 기록만 (기준 01:12 보정, E4 결과 전)
        c.update(e2)
    else:
        rec["e2_3_record_only"] = e2
    rec["limits"] = ["seq: ULog mission_result 기록 주기로 솎임 — 끝 도달·단조만 확인, 경유점 누락 없음과 동등하지 않음 (미확인)",
                     "Gazebo 속도 = 0.2 s 창 위치 차분 (창 중심 시각, 필터 지연 ≈ 0.1 s)"]
    # (v3) 0e 500 Hz 적용: imu_rate_<tag>.json (WSL imu_rate_check.py) — vehicle_imu_status accel_rate 500, delta_velocity_dt 4000
    try:
        ir = json.load(open(O / f"imu_rate_{tag}.json", encoding="utf-8"))
        rec["imu_rate"] = ir
        c["0e_imu500_applied"] = abs(ir.get("accel_rate_hz_median", 0) - 500) < 5 and abs(ir.get("dv_dt_us_median", 0) - 4000) < 1
    except Exception:  # noqa: BLE001
        c["0e_imu500_applied"] = None
    # (v3) 0h 정상 도착 회차에 정지 경로(중단) 없음 — F1/항목화 플래그는 켜져 있어도 중단 때만 동작
    c["0h_no_stop_path"] = not any(e["event"] == "STOP_PATH" for e in ev)
    # (v3) 0i 서버가 실제로 읽은 환경 (road_test health.env) — 플래그 값 기록. STOP_PATH 없음만으로 비활성 분기 플래그 값을 입증하지 않음 (Codex 0728)
    env = ((d.get("health") or {}).get("env")) or {}
    want = {"UGV_STOP_CAP_FIRST": "1", "UGV_STOP_ITEMS_RAMP": "1", "UGV_PX4_END_EXTEND": "1", "UGV_PX4_PARK_AFTER_S": None,   # (ops)
            "UGV_MODEL_VARIANT": "susp_a_acc3_imu500", "UGV_TEST_HOOKS": "0", "ADAIR_RUN_ID": tag, "UGV_PX4_STALL_DETECT": "1",
            "UGV_STOP_SPEED_CMD": "0", "UGV_STOP_GRADE": "0", "UGV_SPEED_TERRAIN": "0", "UGV_SPEED_TERRAIN_CMD": "0"}
    rec["server_env"] = {k: env.get(k) for k in want}
    c["0i_server_flags"] = None if not env else all(env.get(k) == v for k, v in want.items())
    if not valid:
        rec["status"] = "INVALID"
    elif any(v is False for v in c.values()):
        rec["status"] = "FAIL"            # (v3) FAIL 우선
    elif any(v is None for v in c.values()):
        rec["status"] = "UNCONFIRMED"
    else:
        rec["status"] = "PASS"
    return rec


tags = sorted({Path(p).name.rsplit("_", 2)[0] for p in glob.glob(str(HK / f"logs/ugv/{PFX}*_*.json"))})
res = [judge(t) for t in tags]
json.dump(res, open(O / f"{PFX}judge_v3.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for r in res:
    print(r["tag"], r.get("status"), {k: v for k, v in r["checks"].items()}, "dest", r.get("final_stop_to_service_dest_m"), "align", r.get("align"))
