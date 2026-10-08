# ugv/road_news.py — 도로 AI 가 찾아 읽는 교통 기사 (RAG 의 검색 쪽)
#
# 기사 묶음: ugv/scenarios/road_news.json (UGV_AGENT_NEWS). 모두 직접 만든 가상 기사다.
#   {"id", "published": "00:05"(시나리오 시각), "road_ids": [...], "title", "body"}
# 검색 순서
#   1. 메타데이터 거르기 — 지금 시각까지 나온 기사만 (미래 기사는 못 읽는다). road_ids 를 주면 그 도로를 다룬 기사만,
#      그런 기사가 없으면 시각만 거른 전체에서 찾는다 (결과에 road_filter="relaxed")
#   2. 점수 — BM25(낱말 + 글자 두 개 묶음) 와 임베딩 코사인 유사도를 반씩. 임베딩 함수가 없거나 실패하면 BM25 만
# 계산은 numpy. 기사 임베딩은 처음 쓸 때 한 번 만들어 기억한다 (기사 내용이 바뀌면 다시).

import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np

from .scenario import fmt_time, parse_time

K1, B = 1.5, 0.75


def tokens(text: str) -> list[str]:
    """한국어 기사용 간단한 토큰: 낱말(문장부호 제거) + 낱말 안의 글자 두 개 묶음. 형태소 분석 없이 조사 붙은 말도 맞힌다."""
    out = []
    for w in re.findall(r"[0-9A-Za-z가-힣]+", text.lower()):
        out.append(w)
        if len(w) >= 2 and re.search(r"[가-힣]", w):
            out.extend(w[i:i + 2] for i in range(len(w) - 1))
    return out


class RoadNews:
    def __init__(self, articles: list[dict], seconds_per_env_step: float = 60.0, embed=None, source: str = ""):
        """embed: (texts: list[str], task: "RETRIEVAL_DOCUMENT"|"RETRIEVAL_QUERY") → list[list[float]], 또는 None."""
        self.source = source
        self.embed = embed
        self.articles = []
        for a in articles:
            self.articles.append({**a, "published_s": parse_time(a.get("published"), seconds_per_env_step, 0.0),
                                  "road_ids": [str(r) for r in a.get("road_ids") or []]})
        self._docs = [tokens(f"{a['title']} {a['body']}") for a in self.articles]
        self._df: dict[str, int] = {}
        for d in self._docs:
            for t in set(d):
                self._df[t] = self._df.get(t, 0) + 1
        self._avgdl = (sum(len(d) for d in self._docs) / len(self._docs)) if self._docs else 1.0
        self._emb: np.ndarray | None = None
        self._emb_key = None

    @classmethod
    def load(cls, path: str | Path, seconds_per_env_step: float = 60.0, embed=None) -> "RoadNews":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d.get("articles", []), seconds_per_env_step, embed, source=d.get("source", str(path)))

    # --- 점수 ------------------------------------------------------------
    def _bm25(self, q: list[str], i: int) -> float:
        doc, n = self._docs[i], len(self._docs)
        tf: dict[str, int] = {}
        for t in doc:
            tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for t in set(q):
            if t not in tf:
                continue
            idf = math.log(1 + (n - self._df[t] + 0.5) / (self._df[t] + 0.5))
            s += idf * tf[t] * (K1 + 1) / (tf[t] + K1 * (1 - B + B * len(doc) / self._avgdl))
        return s

    def _doc_vectors(self) -> np.ndarray | None:
        key = hashlib.sha1("".join(a["id"] + a["title"] + a["body"] for a in self.articles).encode()).hexdigest()
        if self._emb is None or self._emb_key != key:
            vecs = self.embed([f"{a['title']}\n{a['body']}" for a in self.articles], "RETRIEVAL_DOCUMENT")
            m = np.asarray(vecs, dtype=float)
            self._emb = m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-12)
            self._emb_key = key
        return self._emb

    # --- 검색 ------------------------------------------------------------
    def search(self, query: str, now_s: float, road_ids: list[str] | None = None, k: int = 3) -> dict:
        """지금 시각까지 나온 기사 중 query·road_ids 에 맞는 상위 k 개.
        반환: {"hits": [{id, title, body, published, road_ids, score, bm25, cosine}], "road_filter", "method"}"""
        visible = [i for i, a in enumerate(self.articles) if a["published_s"] <= now_s]
        want = {str(r) for r in road_ids or []}
        road_filter = "none"
        pool = visible
        if want:
            pool = [i for i in visible if want & set(self.articles[i]["road_ids"])]
            road_filter = "matched"
            if not pool:
                pool, road_filter = visible, "relaxed"
        if not pool:
            return {"hits": [], "road_filter": road_filter, "method": "none", "visible": 0}
        q = tokens(query or "")
        bm = np.array([self._bm25(q, i) for i in pool])
        bm_n = bm / bm.max() if bm.max() > 0 else bm
        cos, method = None, "bm25"
        if self.embed is not None and query:
            try:
                docs = self._doc_vectors()
                qv = np.asarray(self.embed([query], "RETRIEVAL_QUERY")[0], dtype=float)
                qv = qv / max(np.linalg.norm(qv), 1e-12)
                cos = docs[pool] @ qv
                method = "bm25+embedding"
            except Exception as e:   # noqa: BLE001 — 임베딩이 안 되면 BM25 만
                method = f"bm25 (임베딩 실패: {type(e).__name__})"
        score = bm_n if cos is None else 0.5 * bm_n + 0.5 * (cos + 1) / 2
        order = np.argsort(-score)[:k]
        hits = []
        for j in order:
            a = self.articles[pool[j]]
            hits.append({"id": a["id"], "title": a["title"], "body": a["body"], "published": fmt_time(a["published_s"]),
                         "road_ids": a["road_ids"], "score": round(float(score[j]), 3), "bm25": round(float(bm[j]), 3),
                         "cosine": None if cos is None else round(float(cos[j]), 3)})
        return {"hits": hits, "road_filter": road_filter, "method": method, "visible": len(visible)}
