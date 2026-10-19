# -*- coding: utf-8 -*-
"""
orchestrator/knowledge.py
=========================
"총괄이 아는 세계" (사용자 결정 2026-09-30: 정답지 방지).

환경 시뮬레이터는 진짜 세계다. 총괄의 판단은 진짜 상태를 직접 보지 않고,
아래 경로로 알게 된 사실만 쓴다. 모든 사실은 시뮬레이션 시각·출처와 함께 장부(knowledge 표)에 쌓인다.

  FIRE    신고(시나리오 이벤트·외부 API), 정찰 결과(불 발견 / 칸 전체를 봤고 불 없음 / 칸 일부만 봤고 불 없음)
  WEATHER 기상청 관측소 관측(재생기, 그 시각까지 나온 값만), 현장 모의 측정

판단에 쓰는 "화면(view)" 은 engine.view() 가 만든다:
  지도(변하지 않는 지형·건물·보호대상) + 여기 쌓인 사실 + 분석(위험 칸·확산 예측, 입력은 이 사실만)
"""

import csv
import json
import math
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import config
from .ledger import Ledger

KST = timezone(timedelta(hours=9))
BURNING_STATUSES = ("REPORTED", "CONFIRMED")
# fire_states 가 캐시보다 이른 시각 조회를 칸 단위로 처리하는 범위 (모의 초). 스레드 사이 시각 차이(100배속에서 수백 초)를
# 넉넉히 덮는다. 이보다 이른 시각은 전부 다시 접는다
FIRE_PAST_WINDOW_S = 3600.0


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * 6371000.0 * math.asin(math.sqrt(min(1.0, max(0.0, a))))


def _fold_key(k: dict):
    """ledger.knowledge 의 정렬 순서 (sim_time_s, seq). SQLite 는 NULL 시각을 맨 앞에 둔다"""
    t = k["sim_time_s"]
    return (t is not None, t if t is not None else 0.0, k["seq"])


def _fold_fire(out: Dict[str, dict], k: dict) -> None:
    """FIRE 사실 한 행을 칸별 믿음에 접는다 (Knowledge.fire_states 규칙)"""
    fact = {**k["body"], "sim_time_s": k["sim_time_s"], "source": k["source"]}
    prev = out.get(k["subject"])
    if fact.get("status") == "NOT_DETECTED_PARTIAL":
        partial = {"status": "NOT_DETECTED_PARTIAL", "sim_time_s": k["sim_time_s"], "source": k["source"],
                   "observation_id": fact.get("observation_id"), "resource_id": fact.get("resource_id"),
                   "coverage_fraction": fact.get("coverage_fraction"),
                   "unobserved_fraction": (None if fact.get("coverage_fraction") is None
                                           else round(1.0 - fact["coverage_fraction"], 6))}
        if prev is not None and prev["status"] != "NOT_DETECTED_PARTIAL":
            out[k["subject"]] = {**prev, "last_partial_observation": partial}
        else:
            out[k["subject"]] = {**fact, "last_partial_observation": partial}
    else:
        out[k["subject"]] = fact          # 전체 관측·신고는 믿음을 새로 정한다 (이전 부분 관측 표시는 지운다)


class Knowledge:
    def __init__(self, ledger: Ledger):
        self.ledger = ledger
        self._fire_cache = None                   # fire_states 증분 계산 상태
        self._fire_lock = threading.RLock()

    # ------------------------------------------------------------------ 화재
    def report_fire(self, cell_id: str, sim_time_s: float, source: str, key: str, detail: dict = None) -> bool:
        return self.ledger.add_knowledge("FIRE", key, cell_id, sim_time_s, source,
                                         {"cell_id": cell_id, "status": "REPORTED", **(detail or {})})

    def record_observation(self, obs: dict, sim_time_s: float, extra: dict = None) -> None:
        """정찰 결과. 불을 본 칸은 CONFIRMED(일부만 봤어도 본 사실은 성립),
        칸 전체를 봤는데 불이 없으면 OBSERVED_CLEAR, 칸 일부만 봤고 그 범위에 불이 없으면 NOT_DETECTED_PARTIAL
        (칸 전체에 불이 없다고 단정하지 않는다 — 관측 비율을 함께 남긴다)."""
        found = {d["cell_id"]: d.get("fire_state") for d in obs.get("detections", [])}
        frac = {c["cell_id"]: c.get("fraction") for c in obs.get("cell_coverage", [])}
        full = set(obs.get("covered_cells", []))
        for cid in sorted(full | set(obs.get("partial_cells", [])) | set(found)):
            if found.get(cid) == "BURNING":
                status = "CONFIRMED"
            elif found.get(cid) == "BURNED":
                status = "CONFIRMED_BURNED"
            else:
                status = "OBSERVED_CLEAR" if cid in full else "NOT_DETECTED_PARTIAL"
            self.ledger.add_knowledge("FIRE", f"{obs['observation_id']}:{cid}", cid, sim_time_s,
                                      obs.get("source", "OBSERVATION"),
                                      {"cell_id": cid, "status": status, "observation_id": obs["observation_id"],
                                       "resource_id": obs.get("resource_id"), "coverage_fraction": frac.get(cid),
                                       **(extra or {})})

    def fire_states(self, now_s: float) -> Dict[str, dict]:
        """칸별 현재 믿음 (now 이전 사실을 시각 순서로 접은 결과). 화면·API·분석 입력이 모두 이 결과를 쓴다.

        믿음을 바꾸는 사실: 신고(REPORTED), 불 확인(CONFIRMED·CONFIRMED_BURNED), 칸 전체를 봤고 불 없음(OBSERVED_CLEAR).
        칸 일부만 보고 불을 못 본 관측(NOT_DETECTED_PARTIAL)은 기존 신고·확인을 해소하지 않는다 (R02) —
        믿음은 그대로 두고 last_partial_observation 에 본 범위·시각·출처를 덧붙인다. 새 확률·위험 수치는 만들지 않는다.
        그 칸에 기존 근거가 없을 때만 NOT_DETECTED_PARTIAL 이 그대로 상태가 된다 (화재 후보 아님).
        """
        # 증분 계산: 지난번에 접은 결과에 새 행만 더 접는다. 매번 전부 다시 읽으면 관측이 쌓일수록 느려진다
        # (팀 트윈 시험 2026-10-19: 4분에 2만 행 → 관제판 /priority/board 6 s+, 화면 view() 마다 두 번씩 호출).
        # 결과는 전부 다시 접은 것과 같아야 한다 — 접는 순서(sim_time_s, seq)보다 앞에 끼는 행이 오면 처음부터 다시 접는다.
        # 지난번보다 이른 시각 조회(스레드마다 읽은 시각이 조금씩 다르다 — 배정은 최신, 추적은 주기 시작, 관제판은 요청 시작)는
        # FIRE_PAST_WINDOW_S 안이면 그 사이에 새 사실이 접힌 칸만 다시 접는다. 칸마다 base(창 밖 행을 접은 결과) +
        # recent(창 안 행)를 두어 out[칸] == base[칸] 에 recent[칸] 을 차례로 접은 결과가 되게 유지한다.
        with self._fire_lock:                     # 추적·배정·API 스레드가 함께 부른다
            run = self.ledger.active_run()
            c = self._fire_cache
            if c is not None and c["run"] == run and now_s < c["now"]:
                return self._fire_states_past(c, now_s)
            if c is None or c["run"] != run:
                c = self._fire_cache = {"run": run, "now": now_s, "seq": 0, "mark": None, "out": {}, "pending": [],
                                        "base": {}, "recent": {}}
            new = self.ledger.knowledge_after("FIRE", c["seq"])
            if new:
                c["seq"] = max(k["seq"] for k in new)
            rows = sorted(c["pending"] + new, key=_fold_key)
            if rows and c["mark"] is not None and _fold_key(rows[0]) < c["mark"]:
                # 이미 접은 행보다 앞 순서의 행이 새로 들어옴 → 처음부터
                self._fire_cache = None
                return self.fire_states(now_s)
            c["now"], c["pending"] = now_s, []
            for k in rows:
                if k["sim_time_s"] is not None and k["sim_time_s"] > now_s:
                    c["pending"].append(k)        # 아직 오지 않은 시각의 사실 — 그 시각이 되면 접는다
                    continue
                _fold_fire(c["out"], k)
                c["mark"] = _fold_key(k)
                if k["sim_time_s"] is None:
                    _fold_fire(c["base"], k)      # 시각 불명 사실은 어느 시각 조회에도 들어간다
                else:
                    c["recent"].setdefault(k["subject"], []).append(k)
            edge = now_s - FIRE_PAST_WINDOW_S     # 창 밖으로 나간 행은 base 에 접고 버린다
            for cid in list(c["recent"]):
                lst = c["recent"][cid]
                n = 0
                while n < len(lst) and lst[n]["sim_time_s"] < edge:
                    _fold_fire(c["base"], lst[n])
                    n += 1
                if n == len(lst):
                    del c["recent"][cid]
                elif n:
                    del lst[:n]
            return {cid: dict(v) for cid, v in c["out"].items()}

    def _fire_states_past(self, c: dict, now_s: float) -> Dict[str, dict]:
        """캐시보다 이른 시각 조회 (_fire_lock 안). 캐시의 접은 결과는 바꾸지 않는다."""
        if now_s < c["now"] - FIRE_PAST_WINDOW_S:
            return self._fold_all(self.ledger.knowledge("FIRE"), now_s)
        new = self.ledger.knowledge_after("FIRE", c["seq"])
        # pending 도 본다: 앞선 과거 조회가 (그때 now_s, c["now"]] 사이 행을 pending 에 넣었을 수 있고,
        # 그 행은 c["out"] 에 아직 접히지 않았으므로 지금 now_s 이전이면 빠뜨리게 된다
        if any(k["sim_time_s"] is None or k["sim_time_s"] <= now_s for k in new + c["pending"]):
            return self._fold_all(self.ledger.knowledge("FIRE"), now_s)     # 늦게 들어온 과거 사실 — 드묾
        if new:                                   # 모두 now_s 뒤의 사실 → 다음 전진 조회에서 접는다
            c["seq"] = max(k["seq"] for k in new)
            c["pending"].extend(new)
        out = {cid: dict(v) for cid, v in c["out"].items()}
        for cid, lst in c["recent"].items():
            if lst[-1]["sim_time_s"] <= now_s:
                continue                          # 이 칸은 now_s 뒤에 접힌 사실이 없다 → 캐시 값 그대로
            tmp = {cid: c["base"][cid]} if cid in c["base"] else {}
            for k in lst:
                if k["sim_time_s"] > now_s:
                    break
                _fold_fire(tmp, k)
            if cid in tmp:
                out[cid] = dict(tmp[cid])
            else:
                out.pop(cid, None)
        return out

    @staticmethod
    def _fold_all(rows, now_s: float) -> Dict[str, dict]:
        out = {}
        for k in rows:
            if k["sim_time_s"] is not None and k["sim_time_s"] > now_s:
                continue
            _fold_fire(out, k)
        return out

    def known_fires(self, now_s: float) -> Dict[str, dict]:
        return {c: v for c, v in self.fire_states(now_s).items() if v["status"] in BURNING_STATUSES}

    # ------------------------------------------------------------------ 기상
    # 항목별 최신성·출처 (2026-09-30 D02)
    #   관측시각(sim_time_s)으로 나이를 잰다. 수신시각(received_sim_s)은 기록만 한다.
    #   미래 관측·관측시각 불명 자료는 쓰지 않는다. 한 항목만 있는 현장 측정이 다른 항목을 지우지 않는다.
    #   유효시간: 관측소는 자료 제공 간격(body.provision_interval_s), 현장 측정은 config.FIELD_WEATHER_MAX_AGE_S.
    #   유효시간 정책이 없으면 POLICY_NOT_SET 으로 드러내고 그 값을 유효하다고 보지 않는다.
    def add_weather(self, key: str, sim_time_s: float, source: str, body: dict,
                    received_sim_s: Optional[float] = None) -> bool:
        subject = body.get("station_id") or body.get("cell_id")
        return self.ledger.add_knowledge("WEATHER", key, subject, sim_time_s, source,
                                         {**body, "received_sim_s": received_sim_s})

    @staticmethod
    def _value_ok(item: str, v) -> bool:
        spec = config.WEATHER_ITEMS[item]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            return False
        return (spec["min"] is None or v >= spec["min"]) and (spec["max"] is None or v <= spec["max"])

    @staticmethod
    def _max_age(k: dict, item: str) -> Optional[float]:
        if k["body"].get("kind") == "FIELD":
            return (config.FIELD_WEATHER_MAX_AGE_S or {}).get(item)
        return k["body"].get("provision_interval_s")

    def _judge(self, k: dict, item: str, now_s: float) -> dict:
        """지식 한 행의 한 항목을 지금 쓸 수 있는지. status: VALID / EXPIRED / POLICY_NOT_SET /
        OBSERVED_TIME_UNKNOWN / VALUE_INVALID"""
        t, v, max_age = k["sim_time_s"], (k["body"].get("values") or {}).get(item), self._max_age(k, item)
        age = None if t is None else now_s - t
        if t is None:
            status = "OBSERVED_TIME_UNKNOWN"
        elif not self._value_ok(item, v):
            status = "VALUE_INVALID"
        elif max_age is None:
            status = "POLICY_NOT_SET"
        elif age > max_age:
            status = "EXPIRED"
        else:
            status = "VALID"
        b = k["body"]
        ref = {"value": v, "unit": config.WEATHER_ITEMS[item]["unit"], "status": status, "source": k["source"],
               "observed_sim_s": t, "received_sim_s": b.get("received_sim_s"), "age_s": age, "max_age_s": max_age,
               "key": k["key"]}
        if b.get("kind") == "FIELD":
            ref.update({"basis": "FIELD_AT_TARGET_CELL", "cell_id": b.get("cell_id"),
                        "observation_id": b.get("observation_id")})
        else:
            ref.update({"basis": "NEAREST_STATION", "station_id": b.get("station_id"),
                        "station_name": b.get("station_name"), "observed_kst": b.get("observed_kst")})
        return ref

    @staticmethod
    def _latest_with(rows: List[dict], item: str, now_s: float) -> Optional[dict]:
        """그 항목이 들어 있는 행 중 관측시각이 가장 늦은 것 (미래 제외). 시각을 아는 행이 없으면 시각 불명 행."""
        have = [k for k in rows if item in (k["body"].get("values") or {})]
        timed = [k for k in have if k["sim_time_s"] is not None and k["sim_time_s"] <= now_s]
        if timed:
            return max(timed, key=lambda k: (k["sim_time_s"], k["seq"]))
        untimed = [k for k in have if k["sim_time_s"] is None]
        return untimed[-1] if untimed else None

    def _weather_rows(self):
        rows = self.ledger.knowledge("WEATHER")
        return ([k for k in rows if k["body"].get("kind") == "FIELD"],
                [k for k in rows if k["body"].get("kind") == "STATION"])

    def weather_for(self, lat: Optional[float], lon: Optional[float], cell_id: Optional[str], now_s: float) -> dict:
        """목표 지점에서 판단에 쓸 기상을 항목별로 고른다. 보간하지 않는다.

        항목마다: 목표 칸의 유효한 현장 측정 → 없거나 만료면 가장 가까운 관측소의 유효한 값 → 둘 다 없으면 unknown.
        현장 측정이 만료됐으면(관측소 값으로 바꿨든 못 바꿨든) remeasure 에 재측정 요청을 담는다.
        """
        field_rows, station_rows = self._weather_rows()
        here = [k for k in field_rows if cell_id and k["body"].get("cell_id") == cell_id]
        nearest, dist = None, None
        if lat is not None and lon is not None:
            for sid in sorted({k["subject"] for k in station_rows if k["subject"]}):
                b = next(k["body"] for k in station_rows if k["subject"] == sid)
                if b.get("lat") is None or b.get("lon") is None:
                    continue
                d = _haversine_m(lat, lon, b["lat"], b["lon"])
                if dist is None or d < dist:
                    nearest, dist = sid, d
        at_station = [k for k in station_rows if k["subject"] == nearest] if nearest else []
        items, unknown, remeasure = {}, {}, []
        for item in config.WEATHER_ITEMS:
            fk, sk = self._latest_with(here, item, now_s), self._latest_with(at_station, item, now_s)
            f = self._judge(fk, item, now_s) if fk else None
            st = self._judge(sk, item, now_s) if sk else None
            if st:
                st["distance_m"] = round(dist, 1)
            if f and f["status"] == "VALID":
                items[item] = f
                continue
            if st and st["status"] == "VALID":
                items[item] = {**st, "replaced": None if f is None else
                               {k: f[k] for k in ("basis", "status", "value", "observed_sim_s", "age_s",
                                                  "max_age_s", "key", "source")}}
            else:
                unknown[item] = {"reason": "NO_VALID_SOURCE",
                                 "field": None if f is None else f["status"],
                                 "station": None if st is None else st["status"]}
            if f and f["status"] == "EXPIRED":
                remeasure.append({"item": item, "cell_id": cell_id, "expired_key": f["key"],
                                  "expired_observed_sim_s": f["observed_sim_s"]})
        out = {"values": {i: r["value"] for i, r in items.items()}, "items": items, "unknown": unknown,
               "remeasure": remeasure, "simulation_time_s": now_s}
        wind = items.get("wind_ms")
        if wind:       # 풍속 기준 요약 (결정 근거 기록용)
            out.update({k: wind.get(k) for k in ("basis", "source", "station_id", "station_name", "cell_id",
                                                 "distance_m", "observed_kst")})
            out["sim_time_s"] = wind["observed_sim_s"]
        elif not field_rows and not station_rows:
            out["basis"] = "NO_WEATHER_KNOWLEDGE"
        else:
            out["basis"] = "WIND_UNKNOWN"
        return out

    def field_history(self, now_s: float) -> List[dict]:
        """현장 측정 원본 이력 (보관·감사용). 만료 여부를 따지지 않으므로 분석 입력으로 넘기지 않는다."""
        return [{**k["body"], "sim_time_s": k["sim_time_s"], "source": k["source"]}
                for k in self._weather_rows()[0] if k["sim_time_s"] is not None and k["sim_time_s"] <= now_s]

    def field_weather(self, now_s: float) -> dict:
        """칸별 현장 측정 중 지금 유효한 항목만 (분석 입력·화면 공용).
        {"valid": [칸별 유효 값], "excluded": [쓰지 않은 항목과 사유 (값 없음)]}"""
        by_cell = {}
        for k in self._weather_rows()[0]:
            if k["body"].get("cell_id"):
                by_cell.setdefault(k["body"]["cell_id"], []).append(k)
        valid, excluded = [], []
        for cid in sorted(by_cell):
            refs = {}
            for item in config.WEATHER_ITEMS:
                k = self._latest_with(by_cell[cid], item, now_s)
                if k:
                    refs[item] = (self._judge(k, item, now_s), k)
            ok = {i: r for i, (r, _) in refs.items() if r["status"] == "VALID"}
            for i, (r, _) in refs.items():
                if r["status"] != "VALID":
                    excluded.append({"cell_id": cid, "item": i, "status": r["status"], "source": r["source"],
                                     "observed_sim_s": r["observed_sim_s"], "age_s": r["age_s"],
                                     "max_age_s": r["max_age_s"]})
            if ok:
                newest = max((k for i, (_, k) in refs.items() if i in ok), key=lambda k: (k["sim_time_s"], k["seq"]))
                valid.append({"kind": "FIELD", "cell_id": cid, "lat": newest["body"].get("lat"),
                              "lon": newest["body"].get("lon"), "source": newest["source"],
                              "sim_time_s": newest["sim_time_s"], "scope": newest["body"].get("scope"),
                              "values": {i: r["value"] for i, r in ok.items()},
                              "items": {i: {x: r[x] for x in ("status", "unit", "source", "observed_sim_s", "age_s",
                                                              "max_age_s", "observation_id")} for i, r in ok.items()}})
        return {"valid": valid, "excluded": excluded}

    def latest_station_obs(self, now_s: float) -> List[dict]:
        """관측소별 최신 관측 (그 시각까지). values 에는 지금 유효한 항목만 두고, 항목별 상태를 함께 준다."""
        by_station = {}
        for k in self._weather_rows()[1]:
            if k["subject"] and k["sim_time_s"] is not None and k["sim_time_s"] <= now_s:
                by_station.setdefault(k["subject"], []).append(k)
        out = []
        for sid in sorted(by_station):
            rows = by_station[sid]
            newest = max(rows, key=lambda k: (k["sim_time_s"], k["seq"]))
            refs = {i: self._judge(k, i, now_s) for i in config.WEATHER_ITEMS
                    for k in [self._latest_with(rows, i, now_s)] if k}
            out.append({**{x: v for x, v in newest["body"].items() if x != "values"},
                        "sim_time_s": newest["sim_time_s"], "source": newest["source"],
                        "values": {i: r["value"] for i, r in refs.items() if r["status"] == "VALID"},
                        "item_status": {i: {x: r[x] for x in ("status", "observed_sim_s", "age_s", "max_age_s")}
                                        for i, r in refs.items()}})
        return out


# ---------------------------------------------------------------------------
# 기상 관측 공급원
# ---------------------------------------------------------------------------

class KmaAsosReplay:
    """기상청 ASOS 시간자료 재생기. 시뮬레이션 시각까지 관측된 행만 내보낸다 (미래 값 금지)."""

    source = "KMA_ASOS_HOURLY"
    # 자료 제공 간격(시간자료 = 3600초). 다음 관측이 나올 때까지만 최신값으로 본다 (D02 유효시간 근거)
    provision_interval_s = 3600.0
    FIELDS = {"ta": "temperature_c", "ws": "wind_ms", "wd": "wind_dir_deg", "hm": "humidity_pct"}

    def __init__(self, csv_path: Path, stations_path: Path):
        self.rows = list(csv.DictReader(open(csv_path, encoding="utf-8-sig")))
        meta = json.load(open(stations_path, encoding="utf-8"))
        self.stations = meta["stations"]
        self.station_source = meta.get("source")

    def observations(self, sim_time_s: float, scenario_start_kst: Optional[str]) -> List[dict]:
        if not scenario_start_kst:
            return []
        start = datetime.fromisoformat(scenario_start_kst)
        out = []
        for r in self.rows:
            t = datetime.strptime(r["tm"], "%Y-%m-%d %H:%M").replace(tzinfo=KST)
            offset = (t - start).total_seconds()
            if offset > sim_time_s:
                continue
            st = self.stations.get(r["stnId"], {})
            values = {}
            for src, dst in self.FIELDS.items():
                v = (r.get(src) or "").strip()
                if v != "":
                    values[dst] = float(v)
            out.append({"key": f"KMA:{r['stnId']}:{r['tm']}", "sim_time_s": offset, "source": self.source,
                        "body": {"kind": "STATION", "station_id": r["stnId"], "station_name": r.get("stnNm"),
                                 "lat": st.get("lat"), "lon": st.get("lon"), "observed_kst": r["tm"],
                                 "values": values, "station_coord_source": self.station_source,
                                 "provision_interval_s": self.provision_interval_s}})
        return out


class EnvStationFeed:
    """시험용: 환경(진짜 세계)의 기상값을 한 지점 관측소가 잰 것처럼 내보낸다 (TEST_ONLY).
    실제 운용에서는 KmaAsosReplay 같은 관측 자료를 쓴다."""

    source = "FIXTURE_STATION"

    def __init__(self, env, lat: float, lon: float, station_id: str = "FIXTURE"):
        self.env, self.lat, self.lon, self.station_id = env, lat, lon, station_id

    def observations(self, sim_time_s: float, scenario_start_kst: Optional[str]) -> List[dict]:
        values = {k: v for k, v in {"wind_ms": self.env.wind_ms, "wind_dir_deg": self.env.wind_dir_deg,
                                    **(self.env.weather or {})}.items() if v is not None}
        key = f"FIXTURE:{sim_time_s}:{json.dumps(values, sort_keys=True)}"
        return [{"key": key, "sim_time_s": sim_time_s, "source": self.source,
                 "body": {"kind": "STATION", "station_id": self.station_id, "station_name": "시험 관측소",
                          "lat": self.lat, "lon": self.lon, "values": values,
                          # 조회할 때마다 그 시각 값을 새로 내보낸다 → 제공 간격 = 환경 한 틱 (TEST_ONLY)
                          "provision_interval_s": self.env.tick_s}}]


class InjectedAnalysis:
    """분석(위험 칸·확산 예측) 자리의 시험 주입값 (TEST_INJECTED). 환경팀 분석 기능(ENV-04) 전까지 쓴다.

    - 환경(진짜 세계)을 참조하지 않는다. 값은 생성 시 또는 시험이 직접 넣는다 (시나리오 파일의
      injected_analysis). 따라서 진짜 세계의 화재·위험·확산이 바뀌어도 이 값은 바뀌지 않는다.
    - 칸마다 requires_known_fire 를 두면, 총괄이 그 불을 알게 된 뒤(신고·정찰 확인)에만 내보낸다.
    - 내보내는 칸에는 derived_from_observation=False, analysis_source=TEST_INJECTED 를 붙인다.
      관측으로부터 계산한 예측이 아니며, 이 값으로 총괄 예측 성능이 검증됐다고 표시하지 않는다.
    """

    source = "TEST_INJECTED"

    def __init__(self, risk_cells=None, spread_forecast=None, forecast_ref=None):
        self.risk_cells = list(risk_cells or [])
        self.spread_forecast = list(spread_forecast or [])
        self.forecast_ref = forecast_ref
        self.last_input = None

    def _visible(self, cells, known):
        out = []
        for c in cells:
            need = c.get("requires_known_fire")
            needs = [need] if isinstance(need, str) else list(need or [])
            if all(n in known for n in needs):
                out.append({**c, "derived_from_observation": False, "analysis_source": self.source})
        return out

    def analyze(self, belief: dict) -> dict:
        self.last_input = belief
        known = {c["cell_id"] for c in belief.get("known_fires", [])}
        spread = self._visible(self.spread_forecast, known)
        return {"risk_cells": self._visible(self.risk_cells, known), "spread_forecast": spread,
                "forecast_ref": ({**self.forecast_ref, "injected": True} if (self.forecast_ref and spread) else None),
                "source": self.source, "derived_from_observation": False}
