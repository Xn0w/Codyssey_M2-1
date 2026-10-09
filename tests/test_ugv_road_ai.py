# -*- coding: utf-8 -*-
"""도로 AI (ugv/road_ai.py, 봉인 기능) — 가짜 Gemini 로 판단 흐름과 서버 연동을 본다. 실제 Gemini 는 부르지 않는다.

실행 (저장소 루트):  python -m pytest tests/test_ugv_road_ai.py -q
- 2순위 경로: 1순위와 겹침 70% 미만 (ugv/route_alt.py)
- 지식 검색(RAG, ugv/road_news.py·ugv/knowledge): 지금 시각 이후 기사는 안 보임, 도로로 거르기(일반 지침은 함께),
  문단 조각·문서 단위 묶기, 임베딩 디스크 캐시(바뀐 조각만 다시), 평가 질문 hit@3
- 판단: function calling(모델이 검색 → 결정), inline(서버가 기사를 넣음), 실패 시 1순위
- 서버: 주행 중 막힘 → 차를 세우고 AI 에 묻고 → WAIT → 도로가 열리면 원래 길로 이어 도착
"""

import json
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest

from ugv import graph_gpkg
from ugv.road_ai import GeminiClient, RoadAI
from ugv.road_graph import RoadGraph
from ugv.road_news import RoadNews
from ugv.route_alt import best_and_alternative

ROOT = Path(__file__).resolve().parents[1]
NEWS = ROOT / "ugv" / "knowledge"


def test_alternative_route_overlap():
    g = RoadGraph(graph_gpkg.NODES, graph_gpkg.ROADS)
    g.get_road("682501434").blocked = True
    best, alt = best_and_alternative(g, "494949", "494955", 2.0)
    assert best and alt
    assert "682501434" not in best.roads and "682501434" not in alt.roads
    assert alt.overlap_with(best, g) < 0.7 and alt.travel_s >= best.travel_s
    assert sum(r.blocked for r in g.roads()) == 1          # 탐색이 도로 상태를 건드리지 않는다


def test_news_time_and_road_filter():
    n = RoadNews.load(NEWS)
    r = n.search("설악로 통제 해제", 7 * 60, ["682501434"])
    ids = [h["id"] for h in r["hits"]]
    assert r["road_filter"] == "matched" and ids[0] == "N1" and "N4" not in ids    # N4(00:20)는 아직 안 나옴
    assert set(ids) <= {"N1", "N8", "G1", "G3"}             # 그 도로 기사 + 일반 지침만 (다른 도로 기사는 빠짐)
    r = n.search("설악로 통제 해제", 25 * 60, ["682501434"])
    assert r["hits"][0]["id"] == "N4"
    r = n.search("기린로", 7 * 60, ["no-such-road"])
    assert r["road_filter"] == "relaxed" and r["hits"][0]["id"] == "N5"


def test_knowledge_base_chunks_and_kinds():
    from ugv.road_news import chunk_text
    kb = RoadNews.load(NEWS)
    st = kb.stats()
    assert st["news"] >= 5 and st["guide"] >= 2 and st["chunks"] > st["documents"]       # 긴 지침은 여러 조각
    assert all(len(c["text"]) <= 220 for c in kb.chunks)
    assert chunk_text("가.\n\n나.\n\n다.", 5) == ["가. 나.", "다."]                  # 짧은 문단은 합친다
    g = kb.search("통제 때 기다릴지 우회할지", 0, kind="guide")
    assert {h["kind"] for h in g["hits"]} == {"guide"} and g["hits"][0]["id"] == "G1" and g["hits"][0]["published"] is None
    assert kb.search("설악로 통제", 0, kind="news")["hits"][0]["kind"] == "news"


def test_embedding_cache_reuses_vectors(tmp_path):
    calls = []

    def embed(texts, task):
        calls.append((len(texts), task))
        return [[float(len(t) % 5), 1.0, float(i % 3)] for i, t in enumerate(texts)]
    kb = RoadNews.load(NEWS, embed=embed, cache_dir=tmp_path, embed_model="models/test-embed")
    r = kb.search("설악로 통제 해제", 7 * 60, ["682501434"])
    assert r["method"] == "bm25+embedding" and kb.embedded_new == len(kb.chunks)
    assert calls[0] == (len(kb.chunks), "RETRIEVAL_DOCUMENT") and calls[1] == (1, "RETRIEVAL_QUERY")
    assert (tmp_path / "models_test-embed.json").is_file()
    again = RoadNews.load(NEWS, embed=embed, cache_dir=tmp_path, embed_model="models/test-embed")
    again.search("설악로", 7 * 60)
    assert again.embedded_new == 0 and calls[-1] == (1, "RETRIEVAL_QUERY")           # 문서 임베딩은 캐시에서


def test_legacy_json_still_loads(tmp_path):
    f = tmp_path / "news.json"
    f.write_text(json.dumps({"articles": [{"id": "X1", "published": "00:01", "road_ids": ["r1"],
                                           "title": "t", "body": "도로 통제 해제"}]}), encoding="utf-8")
    assert RoadNews.load(f).search("통제", 120, ["r1"])["hits"][0]["id"] == "X1"


def test_rag_eval_baseline():
    from ugv.tools.rag_eval import evaluate
    spec = json.loads((NEWS / "eval.json").read_text(encoding="utf-8"))
    r = evaluate(RoadNews.load(NEWS), spec["questions"], spec["k"], use_embedding=False)
    assert r["n"] >= 20 and set(r["by_level"]) == {"easy", "hard"}
    # BM25 만의 기준선 (2026-10-09): easy hit@3 1.0, hard hit@3 0.9 · MRR 0.8 — 자료를 바꾸면 이 숫자도 다시 잰다
    assert r["by_level"]["easy"]["hit_at_k"] == 1.0 and r["by_level"]["hard"]["hit_at_k"] >= 0.8, r["by_level"]


def _situation(options=("ROUTE_1",)):
    opts = [{"name": o, "eta_s": 600 + 60 * i, "distance_m": 1200, "road_ids": ["682502600"], "road_names": ["신상촌길"],
             "path": ["a", "b"]} for i, o in enumerate(options)]
    return {"now_s": 420, "now_text": "14:52", "resource_id": "A-ugv1", "resource_type": "UGV", "target": "설악로",
            "blocked_road_id": "682501434", "blocked_name": "설악로", "here_name": "설악로", "eta_before_s": 500,
            "options": opts, "to_sim": lambda hhmm: int(hhmm[:2]) * 3600 + int(hhmm[3:5]) * 60 - (14 * 3600 + 45 * 60)}


def _fc(name, args):
    return {"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": name, "args": args}}]}}]}


def test_function_calling_search_then_decide():
    seen = []

    def http(url, headers, body, timeout):
        seen.append(body)
        if ":generateContent" not in url:
            return 404, {}
        if len(body["contents"]) == 1:
            return 200, _fc("search_road_news", {"query": "설악로 통제 언제 풀리나", "road_ids": ["682501434"]})
        return 200, _fc("submit_decision", {"decision": "ROUTE_1", "reason": "40분 통제라 우회가 빠르다", "article_ids": ["N1"]})

    ai = RoadAI(GeminiClient(None, "m", "e", http=http), RoadNews.load(NEWS))
    out = ai.decide(_situation())
    assert out["decision"] == "ROUTE_1" and out["fallback"] is None and out["article_ids"] == ["N1"]
    fr = seen[1]["contents"][-1]["parts"][0]["functionResponse"]
    assert fr["name"] == "search_road_news" and fr["response"]["articles"][0]["id"] == "N1"
    assert [e["type"] for e in out["trace"]] == ["AGENT_REQUEST", "AGENT_TOOL", "AGENT_DECISION"]
    assert seen[0]["toolConfig"]["functionCallingConfig"]["mode"] == "ANY"
    assert "자료가 주어지지 않았으면 search_road_news" in seen[0]["systemInstruction"]["parts"][0]["text"]
    assert out["trace"][1]["chunks"] and out["trace"][1]["chunks"][0].startswith("N1#")


def test_inline_mode_puts_articles_in_prompt_and_wait():
    seen = []

    def http(url, headers, body, timeout):
        seen.append(body)
        return 200, _fc("submit_decision", {"decision": "WAIT", "wait_until": "15:30", "reason": "곧 열린다"})

    ai = RoadAI(GeminiClient(None, "m", "e", http=http), RoadNews.load(NEWS), mode="inline")
    out = ai.decide(_situation())
    prompt = seen[0]["contents"][0]["parts"][0]["text"]
    assert "참고 자료" in prompt and "[N1]" in prompt and "[N4]" not in prompt and "[G1] (지침)" in prompt
    assert [t["name"] for t in seen[0]["tools"][0]["functionDeclarations"]] == ["submit_decision"]
    assert out["decision"] == "WAIT" and out["wait_until_s"] == 45 * 60


def test_fallbacks():
    n = RoadNews.load(NEWS)
    assert RoadAI(GeminiClient(None, "m", "e"), n).decide(_situation())["fallback"] == "API_KEY_MISSING"
    bad = RoadAI(GeminiClient(None, "m", "e", http=lambda *a: (500, {"error": {"message": "x"}})), n).decide(_situation())
    assert bad["decision"] == "ROUTE_1" and bad["fallback"].startswith("RuntimeError")
    # 선택지에 없는 ROUTE_2 → 1순위, 사유 남김
    r2 = RoadAI(GeminiClient(None, "m", "e", http=lambda *a: (200, _fc("submit_decision", {"decision": "ROUTE_2", "reason": "r"}))), n)
    out = r2.decide(_situation())
    assert out["decision"] == "ROUTE_1" and "ROUTE_2" in out["fallback"]
    lim = RoadAI(GeminiClient(None, "m", "e", http=lambda *a: (200, _fc("search_road_news", {"query": "q"}))), n, max_turns=2)
    assert lim.decide(_situation())["fallback"] == "NO_DECISION"


def test_last_turn_only_allows_submit():
    """검색만 되풀이하는 모델도 마지막 차례에는 판단 제출만 고를 수 있다 (실측: 검색 4번 뒤 NO_DECISION)."""
    seen = []

    def http(url, headers, body, timeout):
        names = body["toolConfig"]["functionCallingConfig"]["allowedFunctionNames"]
        seen.append(names)
        if names == ["submit_decision"]:
            return 200, _fc("submit_decision", {"decision": "ROUTE_1", "reason": "r", "article_ids": ["N1"]})
        return 200, _fc("search_road_news", {"query": "q"})

    out = RoadAI(GeminiClient(None, "m", "e", http=http), RoadNews.load(NEWS), max_turns=3).decide(_situation())
    assert [len(x) for x in seen] == [2, 2, 1] and out["decision"] == "ROUTE_1" and not out.get("fallback")


def test_thinking_level_sent_and_dropped_on_400():
    """생각 정도(thinkingLevel)를 실어 보내고, 모델이 400 으로 거부하면 빼고 다시 부른 뒤 이후로도 뺀다."""
    seen = []

    def http(url, headers, body, timeout):
        tc = body.get("generationConfig", {}).get("thinkingConfig")
        seen.append(tc)
        return (400, {"error": {"message": "thinking not supported"}}) if tc else (200, {"ok": 1})

    c = GeminiClient(None, "m", "e", http=http, thinking="low")
    assert c.generate({"generationConfig": {"temperature": 0}}) == {"ok": 1}
    assert c.generate({"generationConfig": {"temperature": 0}}) == {"ok": 1}
    assert seen == [{"thinkingLevel": "low"}, None, None] and c.thinking is None


# --- 서버 연동: 가짜 Gemini 서버 + UGV 서버 ----------------------------------------------

def _port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _fake_gemini(decision="WAIT", delay_s=0.0):
    """첫 호출: 기사 검색, 다음: WAIT(15:40 까지 = 시뮬레이션 00:55 — 시각은 기사 묶음의 scenario_start_kst 14:45 기준)."""
    import uvicorn
    from fastapi import FastAPI, Request
    app, calls = FastAPI(), []

    @app.post("/models/{rest:path}")
    async def gen(rest: str, request: Request):
        body = await request.json()
        calls.append({"rest": rest, "body": body})
        if rest.endswith(":batchEmbedContents"):
            return {"embeddings": [{"values": [float(len(r["content"]["parts"][0]["text"]) % 7), 1.0, 0.5]}
                                   for r in body["requests"]]}
        last = body["contents"][-1]["parts"][0]
        if delay_s:
            import asyncio
            await asyncio.sleep(delay_s)                # 느린 모델 흉내
        if "functionResponse" in last:
            return _fc("submit_decision", {"decision": decision, "wait_until": "15:40",
                                           "reason": "기사 N1 근거", "article_ids": ["N1"]})
        return _fc("search_road_news", {"query": "설악로 통제 해제", "road_ids": ["682501434"]})

    port = _port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    return server, f"http://127.0.0.1:{port}", calls


def test_server_waits_then_continues_original_road(tmp_path):
    from tests.test_ugv_road_view import _start, _stop
    gem, url_g, calls = _fake_gemini()
    scen = tmp_path / "block.csv"
    scen.write_text("kind,target,start,end,value,note\nroad,682501434,00:02,00:20,,시험 통제\n", encoding="utf-8")
    p, url = _start(tmp_path, str(scen), UGV_AGENT="1", UGV_AGENT_API_KEY="test-key", UGV_AGENT_BASE_URL=url_g, UGV_AGENT_NEWS_URL="http://127.0.0.1:{port}",
                    UGV_TIME_SCALE="50")
    try:
        assert httpx.get(url + "/history/runs").json()
        r = httpx.post(url + "/view/command", json={"resource_id": "A-ugv1", "node_id": "494955"}, timeout=30).json()
        assert r["verdict"] == "ACCEPT", r
        tid = r["task_id"]
        end = time.time() + 90
        st = None
        while time.time() < end:
            st = httpx.get(f"{url}/ugv/A-ugv1/task/{tid}").json()
            if st["status"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.5)
        assert st and st["status"] == "COMPLETED", st
        run = httpx.get(url + "/history/runs").json()["current"]
        ev = httpx.get(f"{url}/history/runs/{run}").json()["events"]
        types = [e["type"] for e in ev]
        assert ev[0]["data"]["ugv_agent"] == "ON:function_calling"
        for t in ("AGENT_REQUEST", "AGENT_TOOL", "AGENT_DECISION", "UGV_WAITING", "UGV_REROUTED"):
            assert t in types, t
        req = next(e for e in ev if e["type"] == "AGENT_REQUEST")["data"]
        assert "지금 시각 14:4" in req["prompt"]          # 환경 서버 없이도 기사와 같은 실제 시각 (00:02 = 14:47)
        tool = next(e for e in ev if e["type"] == "AGENT_TOOL")["data"]
        assert tool["source"].startswith("news_api"), tool          # 도로 AI 는 뉴스 사이트 웹 API 로 찾는다
        assert tool["titles"] and len(tool["titles"]) == len(tool["hits"])   # 상황판 도로 AI 탭이 제목을 보여 준다
        dec = next(e for e in ev if e["type"] == "AGENT_DECISION")["data"]
        assert dec["decision"] == "WAIT" and dec["article_ids"] == ["N1"]
        rr = next(e for e in ev if e["type"] == "UGV_REROUTED")
        assert rr["data"]["ai"]["reopened"] is True and rr["sim_time_s"] >= 20 * 60 - 120   # 열릴 때까지 기다렸다
        route = [e for e in ev if e["type"] == "ROUTE"][-1]["data"]
        assert "682501434" in [l["road_id"] for l in route["legs"]]                      # 원래 길로
        assert any(c["rest"].endswith(":generateContent") for c in calls)
        # 기다리는 자리 = 막힌 도로 입구: 대기를 정하면 거기까지 가서 서고, 열리면 바로 막혔던 도로로 들어간다
        first = next(e for e in ev if e["type"] == "ROUTE")["data"]
        entrance = next(l["from"] for l in first["legs"] if l["road_id"] == "682501434")
        wait = next(e for e in ev if e["type"] == "UGV_WAITING")["data"]
        assert wait["hold_node"] == entrance, (wait, entrance)
        moving = [l for l in route["legs"] if l.get("distance_m", 0) > 5]
        assert moving[0]["road_id"] == "682501434", route["legs"][:3]
    finally:
        _stop(p)
        gem.should_exit = True


def test_server_reopen_before_answer_goes_original_road(tmp_path):
    """답이 오기 전에 길이 먼저 열리면 답을 기다리지 않고 원래 길로 간다 (실측: 판단 64초 동안 열린 길 앞에서 대기)."""
    from tests.test_ugv_road_view import _start, _stop
    gem, url_g, _ = _fake_gemini(delay_s=15)
    scen = tmp_path / "block.csv"
    scen.write_text("kind,target,start,end,value,note\nroad,682501434,00:02,00:06,,시험 통제\n", encoding="utf-8")
    p, url = _start(tmp_path, str(scen), UGV_AGENT="1", UGV_AGENT_API_KEY="test-key", UGV_AGENT_BASE_URL=url_g,
                    UGV_AGENT_NEWS_URL="http://127.0.0.1:{port}", UGV_TIME_SCALE="50")
    try:
        r = httpx.post(url + "/view/command", json={"resource_id": "A-ugv1", "node_id": "494955"}, timeout=30).json()
        assert r["verdict"] == "ACCEPT", r
        tid, end, st = r["task_id"], time.time() + 90, None
        while time.time() < end:
            st = httpx.get(f"{url}/ugv/A-ugv1/task/{tid}").json()
            if st["status"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.5)
        assert st and st["status"] == "COMPLETED", st
        run = httpx.get(url + "/history/runs").json()["current"]
        ev = httpx.get(f"{url}/history/runs/{run}").json()["events"]
        dec = next(e for e in ev if e["type"] == "AGENT_DECISION")
        assert dec["data"]["decision"] == "REOPENED", dec
        rr = next(e for e in ev if e["type"] == "UGV_REROUTED")
        assert rr["data"]["ai"]["reopened"] is True and rr["sim_time_s"] < 8 * 60     # 15초(=12.5분) 답을 기다리지 않았다
        route = [e for e in ev if e["type"] == "ROUTE"][-1]["data"]
        assert "682501434" in [l["road_id"] for l in route["legs"]]
    finally:
        _stop(p)
        gem.should_exit = True


def test_server_route2_follows_alternative(tmp_path):
    """AI 가 2순위를 고르면 그 경로로 간다 (1순위와 다른 길)."""
    from tests.test_ugv_road_view import _start, _stop
    gem, url_g, _ = _fake_gemini("ROUTE_2")
    scen = tmp_path / "block.csv"
    scen.write_text("kind,target,start,end,value,note\nroad,682501434,00:02,,,시험 통제\n", encoding="utf-8")
    p, url = _start(tmp_path, str(scen), UGV_AGENT="1", UGV_AGENT_API_KEY="test-key", UGV_AGENT_BASE_URL=url_g, UGV_AGENT_NEWS_URL="http://127.0.0.1:{port}",
                    UGV_TIME_SCALE="50")
    try:
        tid = httpx.post(url + "/view/command", json={"resource_id": "A-ugv1", "node_id": "494955"}, timeout=30).json()["task_id"]
        end, st = time.time() + 90, None
        while time.time() < end:
            st = httpx.get(f"{url}/ugv/A-ugv1/task/{tid}").json()
            if st["status"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.5)
        assert st["status"] == "COMPLETED", st
        run = httpx.get(url + "/history/runs").json()["current"]
        ev = httpx.get(f"{url}/history/runs/{run}").json()["events"]
        req = next(e for e in ev if e["type"] == "AGENT_REQUEST")["data"]
        names = [o["name"] for o in req["options"]]
        rr = next(e for e in ev if e["type"] == "UGV_REROUTED")["data"]
        if "ROUTE_2" in names:
            alt = next(o for o in req["options"] if o["name"] == "ROUTE_2")["road_ids"]
            legs = [l["road_id"] for l in [e for e in ev if e["type"] == "ROUTE"][-1]["data"]["legs"]]
            assert rr["ai"]["decision"] == "ROUTE_2" and all(r in legs for r in alt)
        else:                                  # 2순위가 없으면 1순위로 (사유 남김)
            assert rr["ai"]["decision"] == "ROUTE_1" and rr["ai"]["fallback"]
        assert "682501434" not in [l["road_id"] for l in [e for e in ev if e["type"] == "ROUTE"][-1]["data"]["legs"]]
    finally:
        _stop(p)
        gem.should_exit = True


def test_rrf_fusion_with_embedding(tmp_path):
    """임베딩이 있으면 BM25 순위와 코사인 순위를 RRF 로 합친다 (점수 범위가 달라도 두 검색이 같은 무게)."""
    from ugv.road_news import RRF_K

    def embed(texts, task):          # '해제' 가 들어간 글을 같은 방향으로 — 낱말이 안 겹쳐도 뜻으로 찾는 흉내
        return [[1.0, 0.0] if ("해제" in x or "풀리" in x) else [0.0, 1.0] for x in texts]
    kb = RoadNews.load(NEWS, embed=embed, cache_dir=tmp_path, embed_model="fake")
    r = kb.search("언제 풀리나", 7 * 60, ["682501434"])
    assert r["fusion"] == "rrf" and r["method"] == "bm25+embedding"
    h = r["hits"][0]
    assert h["rank_cosine"] >= 1 and h["rank_bm25"] >= 1
    assert abs(h["score"] - (1 / (RRF_K + h["rank_bm25"]) * (h["bm25"] > 0) + 1 / (RRF_K + h["rank_cosine"]))) < 1e-4
    assert RoadNews.load(NEWS).search("언제 풀리나", 7 * 60)["fusion"] == "bm25_only"


def test_news_api_client_falls_back_to_local():
    from ugv.road_news import NewsApiClient
    local = RoadNews.load(NEWS)

    def boom(url, params, timeout):
        raise ConnectionError("down")
    c = NewsApiClient("http://127.0.0.1:9", local=local, http=boom)
    r = c.search("설악로 통제 해제", 7 * 60, ["682501434"])
    assert r["source"].startswith("local (뉴스 API 실패") and r["hits"][0]["id"] == "N1"
    ok = NewsApiClient("http://x", local=local, http=lambda url, params, to: {"hits": [], "road_filter": "none",
                                                                              "method": "bm25", "params": params})
    r = ok.search("q", 60, ["a", "b"], k=2, kind="guide")
    assert r["source"].startswith("news_api") and r["params"] == {"q": "q", "now_s": 60, "k": 2, "road_ids": "a,b",
                                                                  "kind": "guide"}


def test_news_site_api(tmp_path):
    """가상 뉴스 사이트: 지금 시각까지 나온 자료만 목록·본문·검색에 보인다 (도로 AI 가 꺼져 있어도 사이트는 열린다)."""
    from tests.test_ugv_road_view import _start, _stop
    p, url = _start(tmp_path)
    try:
        assert "인제 도로·교통 소식" in httpx.get(url + "/news").text
        d = httpx.get(url + "/news/api/articles", params={"now_s": 420}).json()
        ids = [a["id"] for a in d["articles"]]
        assert "N1" in ids and "N4" not in ids and d["upcoming"] >= 1 and d["now_kst"] == "14:52"
        assert ids.index("N1") < ids.index("G1")                            # 기사(최신 먼저) 다음 지침
        assert httpx.get(url + "/news/api/articles/N4", params={"now_s": 420}).status_code == 404   # 아직 안 나옴
        a = httpx.get(url + "/news/api/articles/N4", params={"now_s": 25 * 60}).json()
        assert a["published_kst"] == "15:05" and "설악로" in a["road_names"] and a["body"]
        s = httpx.get(url + "/news/api/search", params={"q": "설악로 통제 해제", "road_ids": "682501434",
                                                        "now_s": 420}).json()
        assert s["hits"][0]["id"] == "N1" and s["hits"][0]["published_kst"] == "14:47" and s["fusion"] == "bm25_only"
        g = httpx.get(url + "/news/api/search", params={"q": "기다릴지 우회할지", "kind": "guide", "now_s": 0}).json()
        assert {h["kind"] for h in g["hits"]} == {"guide"}
    finally:
        _stop(p)


def test_agent_dispatch_scenario_matches_routes_and_news():
    """시연 시나리오 2 (ugv/scenarios/agent_dispatch.csv): 막히는 도로가 A·B 의 기본 경로 위에 있고, 기사 시각과 맞는다.
    A: 짧은 통제·우회 +20분 이상 → 대기가 맞는 상황, B: 긴 통제·우회 +10분 미만 → 우회가 맞는 상황."""
    from ugv import config
    from ugv.fleet import GroundFleet
    from ugv.scenario import Scenario
    sc = Scenario.load(ROOT / "ugv" / "scenarios" / "agent_dispatch.csv", 60.0)
    assert len(sc.rules) == 2
    f = GroundFleet(use_px4=False, graph_data=graph_gpkg, time_scale=10)
    g, speed = f.graph, config.RESOURCES[0]["sim_speed_mps"]
    goal = g.nearest_node(38.02845, 128.1309)[0].node_id
    for base, road, min_extra, max_extra in (("A", "682501557", 20, None), ("B", "683400994", 0, 10)):
        r = g.find_route(base, goal, speed)
        assert road in [l["road_id"] for l in g.legs(r.path, speed)]
        g.get_road(road).blocked = True
        extra = (g.find_route(base, goal, speed).eta_s - r.eta_s) / 60
        g.get_road(road).blocked = False
        assert extra >= min_extra and (max_extra is None or extra <= max_extra), (base, extra)
    assert "N10" not in [d["id"] for d in RoadNews.load(NEWS).articles]          # 시나리오 기사는 공통 지식에 없다
    kb = RoadNews.load([NEWS, ROOT / "ugv" / "scenarios" / "agent_dispatch"])
    a_ids = [h["id"] for h in kb.search("통제 해제", 4 * 60, ["682501557"])["hits"]]
    b_ids = [h["id"] for h in kb.search("통제", 3 * 60, ["683400994"])["hits"]]
    assert "N10" in a_ids and "N1" not in a_ids          # 그 도로 기사 + 일반 지침 (다른 설악로 구간 기사는 안 섞임)
    assert "N11" in b_ids and "N10" not in b_ids
    assert "N10" not in [h["id"] for h in kb.search("통제 해제", 2 * 60, ["682501557"])["hits"]]   # 00:03 전엔 없음


def test_scenario_news_folder_follows_scenario(monkeypatch):
    """시나리오 기사는 시나리오 파일 옆 같은 이름 폴더(news/)에서만 읽는다 — 시연 2 와 트윈 기사가 섞이지 않는다."""
    from ugv import config
    monkeypatch.setattr(config, "AGENT_NEWS", "ugv/knowledge")
    monkeypatch.setattr(config, "SCENARIO_FILE", "ugv/scenarios/twin_inje.csv")
    ids = [d["id"] for d in RoadNews.load(config.agent_news_paths(ROOT)).articles]
    assert "N12" in ids and "N13" in ids and "N10" not in ids and "G1" in ids
    monkeypatch.setattr(config, "SCENARIO_FILE", "")
    assert config.agent_news_paths(ROOT) == [str(ROOT / "ugv" / "knowledge")]
    with pytest.raises(ValueError):                                         # 같은 id 를 두 번 읽으면 오류
        RoadNews.load([NEWS, NEWS])


def test_twin_scenario_matches_first_dispatch():
    """트윈 시나리오 (ugv/scenarios/twin_inje.csv): ADAIR 트윈 첫 출동 길(실측)에 통제가 걸리고, 기사와 판단 근거가 맞는다.
    A(인제119→494950): 우회 +분이 '대기 + 여유 10분' 보다 커서 WAIT 이 맞다. B(기린119→494955): 긴 통제·우회 +10분 미만 → ROUTE_1."""
    from ugv import config
    from ugv.fleet import GroundFleet
    from ugv.scenario import Scenario
    sc = Scenario.load(ROOT / "ugv" / "scenarios" / "twin_inje.csv", 60.0)
    rules = {r["targets"][0]: r for r in sc.rules}
    assert set(rules) == {"682501557", "683400994"}
    f = GroundFleet(use_px4=False, graph_data=graph_gpkg, time_scale=100)
    g, speed = f.graph, config.RESOURCES[0]["sim_speed_mps"]
    for base, goal, road, mid in (("A", "494950", "682501557", "682501201"), ("B", "494955", "683400994", "683400633")):
        legs = g.legs(g.find_route(base, goal, speed).path, speed)
        ids = [l["road_id"] for l in legs]
        assert road in ids and mid in ids, (base, ids[:10])                 # 실측 경로와 같은 길
        node = legs[ids.index(mid)]["to"]                                    # 막힘을 알아챌 무렵 차가 있는 곳
        r0 = g.find_route(node, goal, speed)
        g.get_road(road).blocked = True
        extra = (g.find_route(node, goal, speed).eta_s - r0.eta_s) / 60
        g.get_road(road).blocked = False
        closure = (rules[road]["end"] - rules[road]["start"]) / 60
        if base == "A":
            assert extra > closure + config.AGENT_WAIT_GRACE_S / 60, (extra, closure)   # 대기가 이긴다
        else:
            assert extra < 10 and closure > 60                               # 우회가 이긴다
    kb = RoadNews.load([NEWS, ROOT / "ugv" / "scenarios" / "twin_inje"])
    assert "N12" in [h["id"] for h in kb.search("통제 해제", 13 * 60, ["682501557"])["hits"]]
    assert "N13" in [h["id"] for h in kb.search("통제", 13 * 60, ["683400994"])["hits"]]
    assert "N12" not in [h["id"] for h in kb.search("통제 해제", 12 * 60, ["682501557"])["hits"]]   # 14:58 전엔 없음
