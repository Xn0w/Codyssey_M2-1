# -*- coding: utf-8 -*-
"""경사 시험 판정 (차량 개조 계획 T6 기준, 정의는 경사 결과를 보기 전 2026-10-13 12:55 고정).
실행: python logs/ugv/stage6/slope_report.py [--prefix cs_] [--out slope_report.json]   (ADAIR 저장소 루트에서)
회차 = logs/ugv/stage4/<tag>.out (래퍼 무효 표시 확인) + ADAIR_wt_fix/logs/ugv/<tag>_<시각>.json/.csv (road_test).
 - 공통: judge3 (도착·차체 도로 경계·정지 확인) — 중단 회차는 도착을 보지 않고 경계·정지만.
 - 등판 속도 유지 (up): 도로 양끝 30 m(출발 가속·도착 감속)를 뺀 구간에서 Gazebo 실측 속도(0.2 s 창) ≥ 그 지점 계획 속도(마지막 전송 미션 항목 속도,
   최근접 항목) × 0.9 를 표본 95 % 이상이 만족.
 - 정지 유지 (up/down): 정지 확인(0.2 m/s 미만 1 s) 뒤 30 s 동안 수평 이동 ≤ 0.1 m (post-stop 35 s 기록).
 - 하강 제동 (downabort): 중단 명령부터 정지까지 거리(road_test analysis.abort.stop_distance_m) / 같은 회차 서버 STOP_PATH needed_m 의 비율 ≤
   평지 기준 비율 × 1.3. 평지 기준 = chain_s4p UGV 취소 정지 30 km/h (같은 규칙 v²/(2·1.5)+5 m) 의 실제/계획(Gazebo 기준 계획 거리) 비율 중앙값.
 v2 (2026-10-13 추가 보완 2·3·4 — 기존 CSV 재분석, v1 결과 보존):
 - 정지 유지 v2: 도착 회차는 서버 ARRIVED/TASK_COMPLETED 이벤트 시각(wall) 이후에서만, sim_t 기준 0.2 m/s 미만 1 s 연속 구간을 찾고,
   확인 완료(구간 시작 + 1 s) 시점부터 30 s 동안 최대 수평 이동 ≤ 0.1 m. v1(고정 28 표본·출발 대기 포함 가능)은 hold_v1 로 보존.
 - 하강 제동 표기: '하강 실제/계획 거리' 를 '평지 실제/계획 거리' 와 비교한 정규화 지표다 (같은 속도 평지 정지거리의 1.3배가 아님).
   평지 기준 = drive_test cancel30 (8.2 m/s, 정지점 하나 미션·지점 속도 유지, 서버와 같은 정차 유지 정책) / 하강 = 서버 중단(약 9.1 m/s,
   STOP_PATH 계획 경로 정지·서버 정차 유지) — 속도·명령 방식이 다르다.
 - 하강 중단 구간 분리: 명령(STOP_PATH 이벤트 wall) → 감속 시작(명령 때 속도 −0.3 m/s) → 1 m/s 미만 → 정지(0.1 m/s 미만 1 s 연속 시작).
   마지막 구간에 PX4 미션 끝 뒤 저속 진행이 포함된다 (서버 이벤트 없음 — 근사).
 - 기록 한계: 바퀴 관절 속도·모터 명령·토크는 road_test 기록(wheel_rad_s 열)이 비어 있어 미수집 — 이상적 속도 구동이며 실차 견인력 재현 아님.
"""
import argparse
from datetime import datetime
import csv
import glob
import json
import math
import statistics
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]          # ADAIR
G = R.parent
sys.path.insert(0, str(G / "ADAIR_wt_vehicle"))
from ugv.tools import judge3                     # noqa: E402

S4 = R / "logs/ugv/stage4"
LOGS = G / "ADAIR_wt_fix/logs/ugv"
END_EXCL_M, RETAIN, HOLD_S, DRIFT_M, BRAKE_X = 30.0, 0.9, 30.0, 0.1, 1.3


def speed(T, X, Y, i, w=0.1):
    j0, j1 = i, i
    while j0 > 0 and T[i] - T[j0] < w:
        j0 -= 1
    while j1 < len(T) - 1 and T[j1] - T[i] < w:
        j1 += 1
    dt = T[j1] - T[j0]
    return math.hypot(X[j1] - X[j0], Y[j1] - Y[j0]) / dt if dt > 0 else 0.0


def ev_wall(d, names):
    e = next((e for e in d.get("events", []) if e.get("event") in names), None)
    return None if e is None else datetime.fromisoformat(e["timestamp"]).timestamp()


def first_conf(T, V, k0, low=0.2, hold=1.0):
    """k0 이후 sim_t 기준 low 미만이 hold 초 연속인 구간의 시작 (없으면 None)."""
    i = k0
    while i < len(T):
        if V[i] < low:
            j = i
            while j < len(T) and V[j] < low:
                j += 1
            if T[j - 1] - T[i] >= hold:
                return i
            i = j
        else:
            i += 1
    return None


def flat_ref():
    p = R / "logs/ugv/stage6/drive/report_vdr3_3.json"
    rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    rs = []
    for r in rows:
        cb = r.get("command_brake") or {}
        if r["model"] == "adair_ugv" and r["scenario"] == "cancel30" and cb.get("park_mode") == "server" and cb.get("total_travel_cmd_to_confirm_m"):
            rs.append(cb["total_travel_cmd_to_confirm_m"] / cb["planned_dist_from_gz_origin_m"])
    return (statistics.median(rs), rs) if rs else (None, rs)


def analyze(tag):
    out = {"tag": tag}
    for mk in (".contaminated", ".invalid_stop", ".invalid_evidence"):
        if (S4 / f"{tag}{mk}").exists():
            out["status"] = "INVALID"
            out["why"] = mk
            return out
    js = sorted(glob.glob(str(LOGS / f"{tag}_2*[0-9].json")))
    if not js:
        out.update({"status": "INVALID", "why": "결과 JSON 없음"})
        return out
    d = json.loads(Path(js[-1]).read_text(encoding="utf-8"))
    j = judge3.judge(js[-1])
    out["judge3"] = {k: j[k] for k in ("arrived", "inside", "outside_max_m", "stop", "final_pass")}
    rows = list(csv.DictReader(open(js[-1][:-5] + ".csv", encoding="utf-8")))
    T = [float(r["sim_t"]) for r in rows]
    X = [float(r["x"]) for r in rows]
    Y = [float(r["y"]) for r in rows]
    V = [speed(T, X, Y, i) for i in range(len(T))]
    W = [float(r["wall_t"]) for r in rows]
    kw = lambda w: None if w is None else next((i for i in range(len(W)) if W[i] >= w), None)   # noqa: E731
    checks = {}
    aborted = "abort" in tag
    if aborted:
        ab = (d.get("analysis") or {}).get("abort") or {}
        sp = next((e for e in d.get("events", []) if e.get("event") == "STOP_PATH"), None)
        out["abort"] = ab
        out["stop_path"] = None if sp is None else {k: sp.get(k) for k in ("basis", "needed_m", "length_m", "speed_mps", "drivable")}
        out["downhill_trigger"] = d.get("downhill_trigger")
        fr, frs = flat_ref()
        out["flat_ref_ratio"] = None if fr is None else round(fr, 3)
        if ab.get("stop_distance_m") is not None and sp and sp.get("needed_m") and fr:
            ratio = ab["stop_distance_m"] / sp["needed_m"]
            out["downhill_ratio"] = round(ratio, 3)
            checks["downhill_brake_le_flat_x1.3"] = ratio <= fr * BRAKE_X
        else:
            checks["downhill_brake_le_flat_x1.3"] = None
        checks["inside"] = j["inside"]
        checks["stopped_no_remotion"] = bool(ab.get("stopped")) and not ab.get("went_backward_or_uturn") and (ab.get("moved_after_stop_m") or 0) <= DRIFT_M
        # 구간 분리 (기록)
        kc = kw(ev_wall(d, ("STOP_PATH",)))
        if kc is not None:
            kd = next((i for i in range(kc, len(V)) if V[i] < V[kc] - 0.3), None)
            k1 = next((i for i in range(kc, len(V)) if V[i] < 1.0), None)
            ks = first_conf(T, V, kc, low=0.1)
            seg = lambda a, b: None if a is None or b is None or b < a else round(sum(math.hypot(X[q + 1] - X[q], Y[q + 1] - Y[q]) for q in range(a, b)), 2)   # noqa: E731
            out["phase_split_m"] = {"speed_at_cmd_gz_mps": round(V[kc], 2), "cmd_to_decel_start": seg(kc, kd), "decel_to_below_1mps": seg(kd, k1),
                                    "below_1mps_to_stop": seg(k1, ks), "total_gz": seg(kc, ks),
                                    "cmd_to_decel_s": None if kd is None else round(T[kd] - T[kc], 2),
                                    "mean_decel_mps2": None if kd is None or k1 is None or T[k1] <= T[kd] else round((V[kd] - V[k1]) / (T[k1] - T[kd]), 2),
                                    "grade_at_trigger": (d.get("downhill_trigger") or {}).get("grade"),
                                    "basis": "STOP_PATH 이벤트 wall ↔ CSV wall_t, Gazebo 속도(0.2 s 창). 마지막 구간은 PX4 미션 끝 뒤 진행 포함(근사)"}
    else:
        checks["judge3_final_pass"] = j["final_pass"]
        items = (((d.get("runs") or [{}])[0].get("route") or {}).get("last_sent_mission") or {}).get("items") or []
        # 경로상 누적거리 (실측 궤적 기준) — 양끝 30 m 제외
        cum = [0.0]
        for i in range(1, len(X)):
            cum.append(cum[-1] + math.hypot(X[i] - X[i - 1], Y[i] - Y[i - 1]))
        k_stop = next((i for i in range(len(V)) if T[i] > T[0] + 3 and V[i] < 0.2 and all(v < 0.2 for v in V[i:i + 28])), len(V) - 1)
        total = cum[k_stop]
        if items:   # 오르막은 판정, 내리막은 같은 도로 반대 방향 비교 기준(가속·감속 한계와 경사 영향을 가르기 위한 기록 — 판정 아님)
            ok = n = 0
            worst = None
            for i in range(len(X)):
                if END_EXCL_M <= cum[i] <= total - END_EXCL_M:
                    it = min(items, key=lambda q: math.hypot(q[0] - X[i], q[1] - Y[i]))
                    n += 1
                    ok += V[i] >= RETAIN * it[2]
                    r_ = V[i] / it[2] if it[2] > 0 else None
                    worst = r_ if worst is None or (r_ is not None and r_ < worst) else worst
            key = "climb" if "_up_" in tag else "speed_vs_plan_reference_downhill"
            out[key] = {"samples": n, "ratio_ok": round(ok / n, 3) if n else None, "min_speed_over_plan": None if worst is None else round(worst, 3)}
            if "_up_" in tag:
                checks["climb_speed_ge_plan_x0.9"] = (ok / n >= 0.95) if n else None
        # 정지 유지 v2: 도착 이벤트 이후 sim_t 기준 1 s 연속 저속 → 확인 완료부터 30 s 최대 이동
        k_arr = kw(ev_wall(d, ("ARRIVED", "TASK_COMPLETED")))
        if k_arr is None:
            out["hold"] = {"note": "도착 이벤트 시각 없음 — 미확인"}
            checks["hold_drift_le_0.1m_30s"] = None
        else:
            ks = first_conf(T, V, k_arr)
            if ks is None:
                out["hold"] = {"note": "도착 뒤 1 s 연속 정지 없음"}
                checks["hold_drift_le_0.1m_30s"] = None
            else:
                kc2 = next((i for i in range(ks, len(T)) if T[i] >= T[ks] + 1.0), None)
                ke = None if kc2 is None else next((i for i in range(kc2, len(T)) if T[i] >= T[kc2] + HOLD_S), None)
                if ke is None:
                    out["hold"] = {"observed_s": round(T[-1] - T[kc2], 1) if kc2 is not None else 0, "note": "확인 완료 뒤 30 s 관측 부족 — 미확인"}
                    checks["hold_drift_le_0.1m_30s"] = None
                else:
                    drift = max(math.hypot(X[i] - X[kc2], Y[i] - Y[kc2]) for i in range(kc2, ke + 1))
                    out["hold"] = {"drift_m": round(drift, 3), "confirm_sim_t": T[kc2], "arrival_event_sim_idx": k_arr, "z": float(rows[kc2]["z"])}
                    checks["hold_drift_le_0.1m_30s"] = drift <= DRIFT_M
        # v1 (보존): 고정 28 표본, 도착과 연결 안 함
        conf = next((i for i in range(len(V)) if T[i] > T[0] + 3 and all(v < 0.2 for v in V[i:i + 28]) and len(V[i:i + 28]) == 28), None)
        if conf is not None:
            t_end = T[conf] + 1.0 + HOLD_S
            k_end = next((i for i in range(conf, len(T)) if T[i] >= t_end), None)
            if k_end is None:
                out["hold_v1"] = {"observed_s": round(T[-1] - T[conf] - 1.0, 1), "note": "30 s 관측 부족"}
            else:
                k0 = next(i for i in range(conf, len(T)) if T[i] >= T[conf] + 1.0)
                drift = max(math.hypot(X[i] - X[k0], Y[i] - Y[k0]) for i in range(k0, k_end + 1))
                out["hold_v1"] = {"drift_m": round(drift, 3), "pass_v1": drift <= DRIFT_M, "note": "v1 고정 28 표본 — 출발 대기를 잡을 수 있음"}
    out["checks"] = checks
    out["status"] = "UNVERIFIED" if any(v is None for v in checks.values()) or not checks else ("PASS" if all(checks.values()) else "FAIL")
    out["limits"] = "바퀴 관절 속도·모터 명령·토크 미수집 (wheel_rad_s 빈칸) — 이상적 속도 구동"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="cs_")
    ap.add_argument("--logs", default=None, help="road_test 기록 폴더 (기본 ADAIR_wt_fix/logs/ugv; 통합 트리 회차는 ADAIR_wt_integ/logs/ugv)")
    ap.add_argument("--out", default=str(R / "logs/ugv/stage6/slope_report.json"))
    a = ap.parse_args()
    global LOGS
    if a.logs:
        LOGS = Path(a.logs)
    tags = sorted({Path(f).stem for f in glob.glob(str(S4 / f"{a.prefix}*.out"))})
    res = [analyze(t) for t in tags]
    for r in res:
        print(r["tag"], r.get("status"), r.get("checks"), {k: r.get(k) for k in ("climb", "speed_vs_plan_reference_downhill", "hold", "downhill_ratio", "flat_ref_ratio") if r.get(k) is not None})
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
