# ugv/tools/rag_eval.py — 도로 AI 지식 검색 평가 (ugv/knowledge/eval.json)
#
#   python -m ugv.tools.rag_eval              # BM25 만 (키 없이)
#   python -m ugv.tools.rag_eval --embed      # BM25 와 BM25+임베딩을 나란히 (UGV_AGENT_API_KEY 필요, 임베딩은 캐시 사용)
# 지표: 상위 k 안에 맞는 문서가 있는 비율(hit@k), 맞는 문서가 처음 나온 순위의 역수 평균(MRR).
# 질문마다 그 시각(now)까지 나온 자료만 보고, 도로 id 로 거른다 — 실제 판단 때와 같은 조건.

import argparse
import json
import os
from pathlib import Path

from ugv import config
from ugv.road_ai import GeminiClient, load_env_keys
from ugv.road_news import RoadNews
from ugv.scenario import parse_time

ROOT = Path(__file__).resolve().parents[2]


def evaluate(kb: RoadNews, questions: list[dict], k: int, use_embedding: bool) -> dict:
    rows, hit, rr = [], 0, 0.0
    for q in questions:
        now = parse_time(q["now"], 60.0, 0.0)
        res = kb.search(q["query"], now, q.get("road_ids") or None, k=k, use_embedding=use_embedding)
        ids = [h["id"] for h in res["hits"]]
        rank = next((i + 1 for i, d in enumerate(ids) if d in q["expected"]), None)
        hit += rank is not None
        rr += 1.0 / rank if rank else 0.0
        rows.append({"query": q["query"], "now": q["now"], "expected": q["expected"], "got": ids, "rank": rank,
                     "method": res["method"], "road_filter": res["road_filter"]})
    n = len(questions) or 1
    return {"hit_at_k": round(hit / n, 3), "mrr": round(rr / n, 3), "k": k, "n": len(questions), "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--embed", action="store_true")
    ap.add_argument("--k", type=int, default=None)
    a = ap.parse_args()
    base = ROOT / config.AGENT_NEWS
    spec = json.loads((base / "eval.json").read_text(encoding="utf-8"))
    k = a.k or spec.get("k", 3)
    embed = None
    if a.embed:
        load_env_keys(ROOT / ".env")
        key = os.getenv("UGV_AGENT_API_KEY")
        if not key:
            raise SystemExit("UGV_AGENT_API_KEY 가 없습니다")
        embed = GeminiClient(key, config.AGENT_MODEL, config.AGENT_EMBED_MODEL, config.AGENT_BASE_URL,
                             config.AGENT_TIMEOUT_S).embed
    kb = RoadNews.load(base, embed=embed, cache_dir=ROOT / config.AGENT_RAG_CACHE, embed_model=config.AGENT_EMBED_MODEL)
    runs = [("BM25", False)] + ([("BM25+임베딩", True)] if embed else [])
    for name, use in runs:
        r = evaluate(kb, spec["questions"], k, use)
        print(f"== {name}: hit@{k} {r['hit_at_k']}  MRR {r['mrr']}  ({r['n']}문항)")
        for row in r["rows"]:
            mark = "O" if row["rank"] else "X"
            print(f"  {mark} [{row['now']}] {row['query']}  → {row['got']} (정답 {row['expected']}, 순위 {row['rank']})")


if __name__ == "__main__":
    main()
