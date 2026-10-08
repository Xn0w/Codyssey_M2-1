# ugv/history.py — UGV 실행 기록 (도로 상황판의 실시간·과거 조회용)
#
# 서버 한 번 기동 = 실행(run) 하나. {UGV_STATE_DIR}/history/<run_id>.jsonl 에 한 줄씩 덧붙인다.
#   {"seq", "wall", "sim_time_s", "type", "resource_id", "task_id", "data"}
# 무엇을 적나
#   - 총괄 보고와 같은 이벤트 (UGV_EVALUATED·UGV_TASK_STARTED·UGV_PROGRESS·UGV_REROUTED·UGV_ARRIVED·…)
#   - RUN_START   : 자원·거점·시나리오·배율 (재생의 시작 상태)
#   - ROAD_STATE  : 막힌 도로·경유 불가 노드·혼잡·켜진 시나리오 규칙 — 바뀔 때만
#   - ROUTE       : 차가 고른 경로(노드열)와 구간별 소요시간 — 출발·재탐색 때
#   - AGENT_*     : (다음 커밋) 도로 AI 판단·통신. data.roads·data.nodes 에 관련 도로·노드를 싣는다
# 기록은 화면 전용이다. 총괄로 보내지 않고, 실패해도 주행에는 영향이 없다.
# 끄기: UGV_HISTORY=0. 보관 개수: UGV_HISTORY_KEEP (기본 30, 오래된 실행부터 지움)

import json
import logging
import os
import time

log = logging.getLogger(__name__)


class History:
    def __init__(self, state_dir: str, clock=None, enabled: bool = True, keep: int = 30):
        self.dir = os.path.join(state_dir, "history")
        self.clock = clock
        self.enabled = enabled
        self.keep = keep
        self.run_id = time.strftime("%Y%m%dT%H%M%S")
        self.seq = 0
        self.path = os.path.join(self.dir, f"{self.run_id}.jsonl")
        self._fh = None
        self._warned = False
        if enabled:
            try:
                os.makedirs(self.dir, exist_ok=True)
                n = 1
                while os.path.exists(self.path):            # 같은 초에 두 번 떠도 겹치지 않게
                    self.run_id = f"{time.strftime('%Y%m%dT%H%M%S')}-{n}"
                    self.path = os.path.join(self.dir, f"{self.run_id}.jsonl")
                    n += 1
                self._fh = open(self.path, "a", encoding="utf-8")
                self._prune()
            except OSError as e:
                log.warning("실행 기록 끔 (%s): %s", self.dir, e)
                self.enabled = False

    def _prune(self) -> None:
        files = sorted(f for f in os.listdir(self.dir) if f.endswith(".jsonl"))
        for f in files[:-self.keep] if self.keep > 0 else []:
            try:
                os.remove(os.path.join(self.dir, f))
            except OSError:
                pass

    def record(self, type_: str, resource_id: str | None = None, task_id: str | None = None, **data) -> None:
        if not self.enabled or self._fh is None:
            return
        self.seq += 1
        row = {"seq": self.seq, "wall": round(time.time(), 3),
               "sim_time_s": None if self.clock is None else round(self.clock.now(), 1),
               "type": type_, "resource_id": resource_id, "task_id": task_id, "data": data}
        try:
            self._fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            self._fh.flush()
        except (OSError, TypeError, ValueError) as e:
            if not self._warned:
                log.warning("실행 기록 실패: %s", e)
                self._warned = True

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None

    # --- 조회 ---------------------------------------------------------------
    def runs(self) -> list[dict]:
        if not os.path.isdir(self.dir):
            return []
        out = []
        for f in sorted(os.listdir(self.dir), reverse=True):
            if not f.endswith(".jsonl"):
                continue
            rid = f[:-6]
            first = last = None
            n = 0
            try:
                with open(os.path.join(self.dir, f), encoding="utf-8") as fh:
                    for line in fh:
                        n += 1
                        if first is None:
                            first = line
                        last = line
            except OSError:
                continue
            try:
                first_row = json.loads(first) if first else {}
                last_row = json.loads(last) if last else {}
            except ValueError:
                first_row, last_row = {}, {}
            start = first_row.get("data", {}) if first_row.get("type") == "RUN_START" else {}
            out.append({"run_id": rid, "current": rid == self.run_id, "events": n,
                        "started_wall": first_row.get("wall"), "last_wall": last_row.get("wall"),
                        "last_sim_time_s": last_row.get("sim_time_s"),
                        "scenario": start.get("scenario"), "driver": start.get("driver")})
        return out

    def read(self, run_id: str, after: int = 0, limit: int = 20000) -> dict:
        if "/" in run_id or "\\" in run_id or run_id.startswith("."):
            raise KeyError(run_id)
        path = os.path.join(self.dir, f"{run_id}.jsonl")
        if not os.path.exists(path):
            raise KeyError(run_id)
        rows, more = [], False
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue                 # 기록 중이던 마지막 줄
                if row.get("seq", 0) <= after:
                    continue
                if len(rows) >= limit:
                    more = True
                    break
                rows.append(row)
        return {"run_id": run_id, "current": run_id == self.run_id, "events": rows,
                "next_after": rows[-1]["seq"] if rows else after, "more": more}
