# ugv/road_ai.py — 도로 AI: 주행 중 앞길이 막혔을 때 우회·대기를 LLM(Gemini)이 판단한다 [봉인 — 기본 꺼짐]
#
# 켜기: UGV_AGENT=1 (+ UGV_AGENT_API_KEY). sim 드라이버 차량만. 총괄 LLM 과 별개이고 키도 따로 쓴다.
# 언제: 주행 중 남은 경로에 막힌 도로가 생겼을 때 (server._drive_leg 의 재탐색 자리). 차를 세우고 묻는다.
# 무엇을 고르나
#   ROUTE_1  지금 가장 빠른 우회 (AI 를 끈 때와 같은 경로)
#   ROUTE_2  1순위와 겹치는 도로가 70% 미만인 다른 우회 (ugv/route_alt.py, 없으면 선택지에서 빠짐)
#   WAIT     막힌 도로가 곧 열린다고 보고 그 자리에서 기다림 (wait_until 까지, 열리면 바로 출발)
# 근거: 상황(막힌 도로·선택지별 ETA) + 교통 기사(ugv/road_news.py, 가상 기사 묶음)
# 방식 (UGV_AGENT_MODE)
#   function_calling (기본, B): 모델이 search_road_news 도구로 기사를 직접 찾고 submit_decision 으로 결정을 낸다
#   inline (A): 서버가 막힌 도로·경로 도로로 기사를 먼저 찾아 프롬프트에 넣고, 모델은 submit_decision 만 부른다
#   시스템 프롬프트는 같다 — "기사가 주어지지 않았으면 search_road_news 로 먼저 찾아라"
# 실패(키 없음·호출 한도·HTTP 오류·결정 없음·형식 오류)는 모두 ROUTE_1 로 (fallback 에 사유). 주행은 멈추지 않는다.
# 기록: 결과의 trace 를 서버가 실행 기록에 AGENT_REQUEST / AGENT_TOOL / AGENT_DECISION 으로 남긴다.

import json
import os
import time
from pathlib import Path

from .scenario import fmt_time

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
DECISIONS = ("ROUTE_1", "ROUTE_2", "WAIT")

SYSTEM_PROMPT = """너는 산불 현장으로 가는 무인 지상차량(UGV)의 도로 판단 보조다.
주행 중 앞길의 도로가 막혔다. 차는 지금 멈춰 있고 네 판단을 기다린다.
선택지는 상황에 적힌 것만 고를 수 있다.
- ROUTE_1: 지금 가장 빠른 우회 경로
- ROUTE_2: 1순위와 많이 다른 다른 우회 경로 (상황에 없으면 고를 수 없다)
- WAIT: 막힌 도로가 곧 다시 열린다고 볼 근거가 있을 때 그 자리에서 기다린다. wait_until(시각, HH:MM)을 반드시 적는다
판단 근거는 주어진 상황과 교통 기사뿐이다. 기사가 주어지지 않았으면 search_road_news 로 먼저 찾아라.
기사에 없는 사실을 지어내지 마라. 근거가 부족하면 ROUTE_1 을 고른다.
기다리는 시간이 우회로 늘어나는 시간보다 길면 기다리지 않는다.
결정은 submit_decision 으로 낸다. reason 은 한국어 한두 문장, article_ids 에는 근거로 쓴 기사 id 를 적는다."""

TOOL_SEARCH = {
    "name": "search_road_news",
    "description": "지금 시각까지 나온 교통 기사를 찾는다. 도로 id 를 주면 그 도로를 다룬 기사만 찾는다.",
    "parameters": {"type": "object", "properties": {
        "query": {"type": "string", "description": "찾을 내용 (예: 설악로 통제 해제 시각)"},
        "road_ids": {"type": "array", "items": {"type": "string"}, "description": "관련 도로 id (선택)"}},
        "required": ["query"]},
}
TOOL_DECIDE = {
    "name": "submit_decision",
    "description": "우회·대기 결정을 낸다. 이 호출로 판단이 끝난다.",
    "parameters": {"type": "object", "properties": {
        "decision": {"type": "string", "enum": list(DECISIONS)},
        "wait_until": {"type": "string", "description": "WAIT 일 때 기다릴 마지막 시각 HH:MM"},
        "reason": {"type": "string"},
        "article_ids": {"type": "array", "items": {"type": "string"}}},
        "required": ["decision", "reason"]},
}


def load_env_keys(path: Path) -> None:
    """저장소 루트 .env 에서 UGV_ 로 시작하는 값만 환경변수로 (이미 있으면 덮어쓰지 않는다). 키는 코드·로그에 남기지 않는다."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k.startswith("UGV_") and v and k not in os.environ:
            os.environ[k] = v


class GeminiClient:
    """Gemini REST (generateContent·batchEmbedContents). http(url, headers, body, timeout) → (status, dict) 로 바꿔 끼워 시험한다."""

    def __init__(self, api_key: str | None, model: str, embed_model: str, base_url: str = GEMINI_BASE,
                 timeout_s: float = 20.0, http=None):
        self.key, self.model, self.embed_model = api_key, model, embed_model
        self.base, self.timeout_s, self._http = base_url.rstrip("/"), timeout_s, http

    def _post(self, url: str, body: dict) -> dict:
        if self._http is not None:
            status, data = self._http(url, {"x-goog-api-key": "***"}, body, self.timeout_s)
        else:
            import httpx
            r = httpx.post(url, headers={"x-goog-api-key": self.key or ""}, json=body, timeout=self.timeout_s)
            status = r.status_code
            try:
                data = r.json()
            except ValueError:
                data = {"error": {"message": r.text[:300]}}
        if status != 200:
            msg = (data.get("error") or {}).get("message", "") if isinstance(data, dict) else ""
            raise RuntimeError(f"GEMINI_HTTP_{status}: {msg[:200]}")
        return data

    def generate(self, body: dict) -> dict:
        return self._post(f"{self.base}/models/{self.model}:generateContent", body)

    def embed(self, texts: list[str], task: str) -> list[list[float]]:
        body = {"requests": [{"model": f"models/{self.embed_model}", "content": {"parts": [{"text": t}]},
                              "taskType": task} for t in texts]}
        data = self._post(f"{self.base}/models/{self.embed_model}:batchEmbedContents", body)
        return [e["values"] for e in data["embeddings"]]


class RoadAI:
    def __init__(self, client: GeminiClient | None, news, mode: str = "function_calling",
                 max_calls: int = 30, max_turns: int = 4):
        self.client, self.news, self.mode = client, news, mode
        self.max_calls, self.max_turns = max_calls, max_turns
        self.calls = 0

    def status(self) -> str | None:
        """호출할 수 없는 이유. 호출 가능하면 None."""
        if self.client is None or not (self.client.key or self.client._http):
            return "API_KEY_MISSING"
        if self.calls >= self.max_calls:
            return "CALL_LIMIT_REACHED"
        return None

    # --- 상황 글 -----------------------------------------------------------
    @staticmethod
    def situation_text(s: dict) -> str:
        lines = [f"지금 시각 {s['now_text']}. 차량 {s['resource_id']}({s['resource_type']}) 가 목적지 {s['target']} 로 가는 중.",
                 f"앞길의 {s['blocked_name']}(도로 {s['blocked_road_id']}) 가 막혔다. 차는 {s['here_name']} 에 멈춰 있다.",
                 f"막히기 전 남은 시간 예상: {round(s['eta_before_s'] / 60)}분.", "선택지:"]
        for o in s["options"]:
            lines.append(f"- {o['name']}: 남은 시간 약 {round(o['eta_s'] / 60)}분 (원래보다 +{round((o['eta_s'] - s['eta_before_s']) / 60)}분), "
                         f"{o['distance_m'] / 1000:.1f} km, 지나는 도로 {', '.join(o['road_names'])} (id {', '.join(o['road_ids'])})")
        lines.append("- WAIT: 막힌 도로가 열릴 때까지 이 자리에서 대기 (열리면 원래 경로로)")
        return "\n".join(lines)

    # --- 판단 --------------------------------------------------------------
    def decide(self, s: dict) -> dict:
        """s: server 가 만든 상황 (situation_text 의 키 + now_s, to_sim(HH:MM)→초 함수 이름 대신 now/start 정보).
        반환 {decision, wait_until_s, reason, article_ids, mode, fallback, trace, latency_s}"""
        t0 = time.monotonic()
        trace: list[dict] = []
        allowed = {"ROUTE_1", "WAIT"} | ({"ROUTE_2"} if any(o["name"] == "ROUTE_2" for o in s["options"]) else set())

        def fallback(why: str) -> dict:
            out = {"decision": "ROUTE_1", "wait_until_s": None, "reason": f"규칙 판단 (도로 AI 사용 못 함: {why})",
                   "article_ids": [], "mode": self.mode, "fallback": why, "trace": trace,
                   "latency_s": round(time.monotonic() - t0, 2)}
            trace.append({"type": "AGENT_DECISION", **{k: v for k, v in out.items() if k != "trace"}, "wait_until": None})
            return out

        why = self.status()
        if why:
            return fallback(why)
        user = self.situation_text(s)
        tools = [TOOL_SEARCH, TOOL_DECIDE]
        if self.mode == "inline":                   # A: 기사를 먼저 찾아 넣는다
            q = f"{s['blocked_name']} 통제 해제 시각 우회 " + " ".join(n for o in s["options"] for n in o["road_names"])
            road_ids = [s["blocked_road_id"]] + [r for o in s["options"] for r in o["road_ids"]]
            found = self.news.search(q, s["now_s"], road_ids)
            trace.append({"type": "AGENT_TOOL", "tool": "search_road_news", "by": "server", "query": q,
                          "road_ids": road_ids, "hits": [h["id"] for h in found["hits"]], "method": found["method"],
                          "road_filter": found["road_filter"]})
            user += "\n\n참고 기사:\n" + ("\n".join(f"[{h['id']}] ({h['published']}) {h['title']} — {h['body']}"
                                                  for h in found["hits"]) or "(없음)")
            tools = [TOOL_DECIDE]
        contents = [{"role": "user", "parts": [{"text": user}]}]
        trace.append({"type": "AGENT_REQUEST", "mode": self.mode, "model": self.client.model, "prompt": user})
        for _ in range(self.max_turns):
            if self.calls >= self.max_calls:
                return fallback("CALL_LIMIT_REACHED")
            body = {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]}, "contents": list(contents),
                    "tools": [{"functionDeclarations": tools}],
                    "toolConfig": {"functionCallingConfig": {"mode": "ANY",
                                                             "allowedFunctionNames": [t["name"] for t in tools]}},
                    "generationConfig": {"temperature": 0}}
            self.calls += 1
            try:
                data = self.client.generate(body)
                content = data["candidates"][0]["content"]
            except Exception as e:   # noqa: BLE001
                return fallback(f"{type(e).__name__}: {str(e)[:120]}")
            contents.append(content)                 # 받은 그대로 돌려준다 (함수 호출 서명 포함)
            calls = [p["functionCall"] for p in content.get("parts", []) if "functionCall" in p]
            if not calls:
                return fallback("NO_FUNCTION_CALL")
            responses = []
            for c in calls:
                args = c.get("args") or {}
                if c.get("name") == "submit_decision":
                    return self._finish(args, s, allowed, trace, t0)
                if c.get("name") == "search_road_news":
                    found = self.news.search(str(args.get("query", "")), s["now_s"], args.get("road_ids"))
                    trace.append({"type": "AGENT_TOOL", "tool": "search_road_news", "by": "model",
                                  "query": args.get("query"), "road_ids": args.get("road_ids"),
                                  "hits": [h["id"] for h in found["hits"]], "method": found["method"],
                                  "road_filter": found["road_filter"]})
                    payload = {"articles": [{k: h[k] for k in ("id", "published", "title", "body", "road_ids")}
                                            for h in found["hits"]], "road_filter": found["road_filter"]}
                else:
                    payload = {"error": f"없는 도구: {c.get('name')}"}
                responses.append({"functionResponse": {"name": c.get("name"), "response": payload}})
            contents.append({"role": "user", "parts": responses})
        return fallback("NO_DECISION")

    def _finish(self, args: dict, s: dict, allowed: set, trace: list, t0: float) -> dict:
        d = str(args.get("decision", "")).upper()
        reason = str(args.get("reason", ""))[:400]
        ids = [str(x) for x in args.get("article_ids") or []]
        wait_s, note = None, None
        if d not in allowed:
            note, d = f"선택지에 없는 결정 {d or '(빈 값)'} → ROUTE_1", "ROUTE_1"
        elif d == "WAIT":
            try:
                wait_s = s["to_sim"](str(args.get("wait_until", "")))
            except Exception:   # noqa: BLE001
                wait_s = None
            if wait_s is None or wait_s <= s["now_s"]:
                note, d, wait_s = f"wait_until 형식 오류·과거 시각({args.get('wait_until')}) → ROUTE_1", "ROUTE_1", None
        out = {"decision": d, "wait_until_s": wait_s, "reason": reason, "article_ids": ids, "mode": self.mode,
               "fallback": note, "trace": trace, "latency_s": round(time.monotonic() - t0, 2),
               "model_decision": str(args.get("decision", ""))}
        trace.append({"type": "AGENT_DECISION", **{k: v for k, v in out.items() if k != "trace"},
                      "wait_until": None if wait_s is None else fmt_time(wait_s)})
        return out
