"""E4 회차 판정 (기준 logs/ugv/stage6/e4/E4_criteria.md, 실행 전 고정). ADAIR 루트에서: python logs/ugv/stage6/e4/e4_judge.py
입력: road_test 기록 ../ADAIR_wt_hook/logs/ugv/<tag>_*.json/.csv, ULog 덤프 logs/ugv/stage6/e4/ulog_<tag>.json (e4_ulog_dump.py, WSL),
slope_report e4_slope_report.json (judge3·hold v2), 래퍼 rc logs/ugv/stage4/rc_<tag>.json.
Gazebo↔ULog 시각 정렬: Gazebo 속도(위치 차분, sim_t) 와 ULog 지역 위치 속도의 rms 최소 오프셋 (E2 방식). rms 기록."""
import glob
import json
import math
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[4]          # ADAIR
import os
HK = R.parent / os.getenv("E4_TREE", "ADAIR_wt_hook")      # 검증용: E4_TREE=ADAIR_wt_integ_next E4_PREFIX=e3
PFX = os.getenv("E4_PREFIX", "e4")
sys.path.insert(0, str(HK))
from ugv.geo import GZ_FRAME  # noqa: E402

O = R / "logs/ugv/stage6/e4"
CASES = {"e4_acc3_s1096": ("acc3", -2.48), "e4_raoff_s1096": ("raoff", -2.45), "e4_acc3_s3113": ("acc3", None),
         "e3acc": ("acc3", -2.48), "e3base": ("raoff", -2.45)}       # e3* = 판정기 검증용 (연장 없음이라 1·2 는 실패가 정상)
SR = {}
try:
    SR = {r["tag"]: r for r in json.load(open(O / "e4_slope_report.json", encoding="utf-8"))}
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


def judge(tag):
    kind = next(v for k, v in CASES.items() if tag.startswith(k))
    rec = {"tag": tag, "kind": kind[0], "checks": {}}
    c = rec["checks"]
    try:
        rec["wrapper_rc"] = json.load(open(R / f"logs/ugv/stage4/rc_{tag}.json", encoding="utf-8"))
    except Exception:  # noqa: BLE001
        rec["wrapper_rc"] = None
    js = sorted(glob.glob(str(HK / f"logs/ugv/{tag}_*.json")))
    if not js:
        rec["status"] = "NO_RECORD"; return rec
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
                               and es.get("RA_ACC_RAD_MAX") == 3.0 and pp.get("after_s") == 2.0 and pp.get("test_hook") is True)
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
        u = json.load(open(O / f"ulog_{tag}.json", encoding="utf-8"))
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
        b = next((t for t, v in gz_u if fin - 2.0 <= t <= fin + 1.5 and t < dis and v < 0.2), None)
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
                       "disarm_minus_3b": None if b is None else round(dis - b, 3)}
        v_dis = next((v for t, v in gz_u if t >= dis), None)
        runaway = dis - fin >= 4.0 - 0.1 and (v_dis is None or v_dis >= 0.3)   # RUNAWAY 4 s 상한 경로 (서버 로그엔 last_error 가 없어 ULog·Gazebo 로 판정)
        rec["e2_3"].update(disarm_minus_finished=round(dis - fin, 3), gz_speed_at_disarm=v_dis, runaway=runaway)
        e2 = {"7b": b is not None, "7c": b is not None and run_end is not None and run_end - b >= 1.0,
              "7d": b is not None and after <= dis - b <= after + 0.6, "7e_no_runaway": not runaway}
    else:
        e2 = {"7b": False, "7c": False, "7d": False, "7e_no_runaway": False}
    if kind[0] == "acc3":          # ③ 은 PX4 끝 지점 자체 정지 차에만 정의 (E2). RA −1 차는 기록만 (기준 01:12 보정, E4 결과 전)
        c.update(e2)
    else:
        rec["e2_3_record_only"] = e2
    rec["status"] = "PASS" if all(c.values()) else "FAIL"
    return rec


tags = sorted({Path(p).name.rsplit("_", 2)[0] for p in glob.glob(str(HK / f"logs/ugv/{PFX}*_*.json"))})
res = [judge(t) for t in tags]
json.dump(res, open(O / f"{PFX}_judge.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for r in res:
    print(r["tag"], r.get("status"), {k: v for k, v in r["checks"].items()}, "dest", r.get("final_stop_to_service_dest_m"), "align", r.get("align"))
