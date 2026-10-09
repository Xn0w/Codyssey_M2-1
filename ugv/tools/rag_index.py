# ugv/tools/rag_index.py — 도로 AI 지식 베이스 점검·색인 (임베딩 캐시 미리 만들기)
#
#   python -m ugv.tools.rag_index            # 문서·조각 목록, 캐시 상태 (키 없이도 된다)
#   python -m ugv.tools.rag_index --embed    # 캐시에 없는 조각만 임베딩해 저장 (UGV_AGENT_API_KEY 필요)
# 키: UGV_AGENT_API_KEY (환경변수 또는 저장소 루트 .env). 임베딩 모델: UGV_AGENT_EMBED_MODEL

import argparse
import os
from pathlib import Path

from ugv import config
from ugv.road_ai import GeminiClient, load_env_keys
from ugv.road_news import RoadNews

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--embed", action="store_true", help="캐시에 없는 조각을 임베딩해 저장")
    ap.add_argument("--chunks", action="store_true", help="조각 본문까지 출력")
    a = ap.parse_args()
    embed = None
    if a.embed:
        load_env_keys(ROOT / ".env")
        key = os.getenv("UGV_AGENT_API_KEY")
        if not key:
            raise SystemExit("UGV_AGENT_API_KEY 가 없습니다 (.env 에 UGV_AGENT_API_KEY=... 한 줄)")
        embed = GeminiClient(key, config.AGENT_MODEL, config.AGENT_EMBED_MODEL, config.AGENT_BASE_URL,
                             config.AGENT_TIMEOUT_S).embed
    kb = RoadNews.load(ROOT / config.AGENT_NEWS, embed=embed, cache_dir=ROOT / config.AGENT_RAG_CACHE,
                       embed_model=config.AGENT_EMBED_MODEL)
    print(f"지식 베이스 {config.AGENT_NEWS} — {kb.source}")
    for d in kb.articles:
        chunks = [c for c in kb.chunks if kb.articles[c["doc"]] is d]
        when = d.get("published") or "언제나"
        print(f"  [{d['id']}] {d['kind']:5} {when:>5}  조각 {len(chunks)}  도로 {len(d['road_ids'])}개  {d['title']}")
        if a.chunks:
            for c in chunks:
                print(f"      {c['chunk_id']}: {c['text']}")
    if embed is not None:
        kb.build_index()
        print(f"임베딩: 새로 {kb.embedded_new}개, 캐시 {kb.cache.path}")
    print(f"통계: {kb.stats()}")


if __name__ == "__main__":
    main()
