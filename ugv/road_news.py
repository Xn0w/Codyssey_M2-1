# ugv/road_news.py — 도로 AI 의 지식 베이스 검색 (RAG 의 검색 쪽)
#
# 지식 베이스: ugv/knowledge/ (UGV_AGENT_NEWS). 모두 직접 만든 가상 자료다 (실제 보도·실제 지침 아님).
#   meta.json        이름, 출처 표기, scenario_start_kst (자료 시각 00:00 의 실제 시각)
#   news/*.md        교통 기사 — published(시나리오 시각) 이후에만 보인다, road_ids 로 도로와 묶인다
#   guides/*.md      도로 운영 지침 — 언제나 보인다, road_ids 가 없으면 모든 도로에 해당
#   eval.json        검색 평가 질문 (ugv/tools/rag_eval.py)
#   문서 머리말 (--- 사이): id, kind(news|guide), published(HH:MM, 기사만), road_ids(쉼표), title
#   예전 형식 road_news.json(기사 배열)도 그대로 읽는다.
#
# 처리 순서
#   1. 적재·조각내기 — 문서를 문단 단위로 자르고 짧은 문단은 합쳐 조각(chunk, 최대 CHUNK_CHARS 자)을 만든다.
#      조각마다 문서 제목을 앞에 붙여 검색한다 (제목 없는 조각이 엉뚱하게 뽑히지 않게)
#   2. 색인 — BM25(낱말 + 글자 두 개 묶음) 통계, 임베딩은 처음 쓸 때 한 번 만든다.
#      임베딩은 디스크 캐시(UGV_AGENT_RAG_CACHE, 모델별 파일)에 '조각 내용 해시 → 벡터'로 남겨 바뀐 조각만 다시 만든다
#   3. 검색 — 메타데이터로 거른다: 지금 시각까지 나온 것만(미래 기사는 못 읽는다), kind, 도로 id
#      (그 도로를 다룬 문서 + 도로를 정하지 않은 일반 지침. 하나도 없으면 시각만 거른 전체에서 찾고 road_filter="relaxed")
#      → 순위 합치기 RRF(Reciprocal Rank Fusion): BM25 순위와 임베딩 코사인 순위를 각각 매겨
#        점수 = 1/(RRF_K + BM25 순위) + 1/(RRF_K + 코사인 순위). 두 점수의 범위가 달라도 두 검색이 같은 무게로 반영된다.
#        임베딩이 없거나 실패하면 BM25 만 (점수 = BM25 ÷ 그 검색의 최고 BM25)
#      → 문서 단위로 묶어 상위 k 개 문서, 문서마다 맞은 조각(최대 2개)을 본문으로 돌려준다
# 계산은 numpy. 결과의 id 는 문서 id(N1, G1 …)라 판단의 근거 표기(article_ids)에 그대로 쓴다.

import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np

from .scenario import fmt_time, parse_time

K1, B = 1.5, 0.75
RRF_K = 60                 # RRF 상수 (널리 쓰는 기본값). 순위 차이를 얼마나 완만하게 볼지
CHUNK_CHARS = 220          # 조각 최대 글자 수 (문단을 이 길이까지 합친다)
CHUNKS_PER_DOC = 2         # 검색 결과에서 문서마다 돌려줄 조각 수
KINDS = ("news", "guide")


def tokens(text: str) -> list[str]:
    """한국어 자료용 간단한 토큰: 낱말(문장부호 제거) + 낱말 안의 글자 두 개 묶음. 형태소 분석 없이 조사 붙은 말도 맞힌다."""
    out = []
    for w in re.findall(r"[0-9A-Za-z가-힣]+", text.lower()):
        out.append(w)
        if len(w) >= 2 and re.search(r"[가-힣]", w):
            out.extend(w[i:i + 2] for i in range(len(w) - 1))
    return out


def chunk_text(body: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    """문단(빈 줄) 단위로 자르고, max_chars 를 넘지 않게 이어 붙인다. 한 문단이 길면 문장 단위로 나눈다."""
    parts = []
    for para in re.split(r"\n\s*\n", body.strip()):
        para = " ".join(para.split())
        if not para:
            continue
        if len(para) <= max_chars:
            parts.append(para)
            continue
        cur = ""
        for sent in re.split(r"(?<=[.!?다])\s+", para):
            if cur and len(cur) + 1 + len(sent) > max_chars:
                parts.append(cur)
                cur = sent
            else:
                cur = f"{cur} {sent}".strip()
        if cur:
            parts.append(cur)
    chunks, cur = [], ""
    for p in parts:
        if cur and len(cur) + 1 + len(p) > max_chars:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def _parse_md(text: str) -> tuple[dict, str]:
    """'---' 머리말(key: value) + 본문."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        raise ValueError("머리말(--- … ---)이 없다")
    head = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            head[k.strip()] = v.strip()
    return head, m.group(2)


class EmbeddingCache:
    """'조각 내용 해시 → 벡터' 디스크 캐시. 모델이 바뀌면 다른 파일을 쓴다. path 가 None 이면 메모리에만."""

    def __init__(self, path: Path | None):
        self.path = path
        self.vecs: dict[str, list[float]] = {}
        if path is not None and path.is_file():
            try:
                self.vecs = json.loads(path.read_text(encoding="utf-8")).get("vectors", {})
            except (ValueError, OSError):
                self.vecs = {}

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"vectors": self.vecs}), encoding="utf-8")
        tmp.replace(self.path)


def _read_dir(path: Path) -> tuple[dict, list[dict]]:
    """지식 폴더 하나: (meta.json, news/·guides/ 의 문서들)."""
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8")) if (path / "meta.json").is_file() else {}
    docs = []
    for sub in ("news", "guides"):
        for f in sorted((path / sub).glob("*.md")):
            head, body = _parse_md(f.read_text(encoding="utf-8"))
            try:
                docs.append({"id": head["id"], "kind": head.get("kind", "news" if sub == "news" else "guide"),
                             "published": head.get("published") or None, "title": head["title"],
                             "road_ids": [r.strip() for r in head.get("road_ids", "").split(",") if r.strip()],
                             "body": body.strip(), "file": f"{path.name}/{sub}/{f.name}"})
            except KeyError as e:
                raise ValueError(f"{f}: 머리말에 {e} 가 없다") from None
    return meta, docs


class RoadNews:
    """도로 AI 지식 베이스 (이름은 처음 기사 묶음일 때 그대로). articles = 문서, chunks = 검색 단위."""

    def __init__(self, articles: list[dict], seconds_per_env_step: float = 60.0, embed=None, source: str = "",
                 start_kst: str | None = None, cache_path: Path | None = None, embed_model: str = ""):
        """embed: (texts: list[str], task: "RETRIEVAL_DOCUMENT"|"RETRIEVAL_QUERY") → list[list[float]], 또는 None.
        start_kst: 자료 시각 00:00 의 실제 시각 — 환경 서버가 없을 때 판단 문장의 'HH:MM' 을 자료 본문 시각과 맞춘다."""
        self.source = source
        self.start_kst = start_kst
        self.embed = embed
        self.articles = []
        for a in articles:
            kind = a.get("kind", "news")
            if kind not in KINDS:
                raise ValueError(f"{a.get('id')}: kind 는 {KINDS} 중 하나 ({kind})")
            pub = a.get("published")
            self.articles.append({**a, "kind": kind,
                                  "published_s": parse_time(pub, seconds_per_env_step, 0.0) if pub else 0.0,
                                  "road_ids": [str(r) for r in a.get("road_ids") or []]})
        ids = [a["id"] for a in self.articles]
        if len(ids) != len(set(ids)):
            raise ValueError(f"문서 id 중복: {sorted(i for i in ids if ids.count(i) > 1)}")
        self.chunks = []
        for di, a in enumerate(self.articles):
            for ci, text in enumerate(chunk_text(a["body"])):
                full = f"{a['title']}\n{text}"
                self.chunks.append({"chunk_id": f"{a['id']}#{ci + 1}", "doc": di, "text": text, "full": full,
                                    "hash": hashlib.sha1(full.encode()).hexdigest()})
        self._docs = [tokens(c["full"]) for c in self.chunks]
        self._tf = []
        self._df: dict[str, int] = {}
        for d in self._docs:
            tf: dict[str, int] = {}
            for t in d:
                tf[t] = tf.get(t, 0) + 1
            self._tf.append(tf)
            for t in tf:
                self._df[t] = self._df.get(t, 0) + 1
        self._avgdl = (sum(len(d) for d in self._docs) / len(self._docs)) if self._docs else 1.0
        self._emb: np.ndarray | None = None
        self.cache = EmbeddingCache(cache_path)
        self.embed_model = embed_model
        self.embedded_new = 0                       # 이번 실행에서 새로 만든 조각 임베딩 수 (나머지는 캐시)

    # --- 적재 ------------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path, seconds_per_env_step: float = 60.0, embed=None,
             cache_dir: str | Path | None = None, embed_model: str = "") -> "RoadNews":
        """path: 지식 베이스 폴더(ugv/knowledge) 또는 예전 기사 묶음 JSON.
        폴더 여러 개(목록 또는 쉼표로 이은 문자열)를 주면 합친다 — 공통 지식 + 시나리오 전용 기사
        (ugv/scenarios/<이름>/news/). meta.json(시나리오 시작 시각·출처)은 첫 폴더 것을 쓴다. 같은 id 는 오류."""
        cache = None
        if cache_dir is not None and embed is not None:
            safe = re.sub(r"[^0-9A-Za-z._-]", "_", embed_model or "embed")
            cache = Path(cache_dir) / f"{safe}.json"
        paths = [Path(p) for p in (path if isinstance(path, (list, tuple)) else str(path).split(",")) if str(p).strip()]
        if all(p.is_dir() for p in paths):
            meta, docs = {}, []
            for i, p in enumerate(paths):
                m, d = _read_dir(p)
                meta = m if i == 0 else meta
                docs += d
            seen = [d["id"] for d in docs]
            dup = sorted({x for x in seen if seen.count(x) > 1})
            if dup:
                raise ValueError(f"지식 베이스 id 중복: {dup} ({', '.join(map(str, paths))})")
            return cls(docs, seconds_per_env_step, embed, source=meta.get("source", str(paths[0])),
                       start_kst=meta.get("scenario_start_kst"), cache_path=cache, embed_model=embed_model)
        path = paths[0]
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(d.get("articles", []), seconds_per_env_step, embed, source=d.get("source", str(path)),
                   start_kst=d.get("scenario_start_kst"), cache_path=cache, embed_model=embed_model)

    def stats(self) -> dict:
        kinds = {k: sum(1 for a in self.articles if a["kind"] == k) for k in KINDS}
        return {"documents": len(self.articles), **kinds, "chunks": len(self.chunks),
                "cached_vectors": sum(1 for c in self.chunks if c["hash"] in self.cache.vecs)}

    # --- 점수 ------------------------------------------------------------
    def _bm25(self, q: list[str], i: int) -> float:
        tf, n, dl = self._tf[i], len(self._docs), len(self._docs[i])
        s = 0.0
        for t in set(q):
            if t not in tf:
                continue
            idf = math.log(1 + (n - self._df[t] + 0.5) / (self._df[t] + 0.5))
            s += idf * tf[t] * (K1 + 1) / (tf[t] + K1 * (1 - B + B * dl / self._avgdl))
        return s

    def build_index(self) -> np.ndarray | None:
        """조각 임베딩 (캐시에 없는 것만 새로 만든다). 임베딩 함수가 없으면 None."""
        if self.embed is None:
            return None
        if self._emb is None:
            missing = [c for c in self.chunks if c["hash"] not in self.cache.vecs]
            if missing:
                vecs = self.embed([c["full"] for c in missing], "RETRIEVAL_DOCUMENT")
                for c, v in zip(missing, vecs):
                    self.cache.vecs[c["hash"]] = [float(x) for x in v]
                self.embedded_new += len(missing)
                self.cache.save()
            m = np.asarray([self.cache.vecs[c["hash"]] for c in self.chunks], dtype=float)
            self._emb = m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-12)
        return self._emb

    # --- 검색 ------------------------------------------------------------
    def search(self, query: str, now_s: float, road_ids: list[str] | None = None, k: int = 3,
               kind: str | None = None, use_embedding: bool = True) -> dict:
        """지금 시각까지 나온 문서 중 query·road_ids·kind 에 맞는 상위 k 개 문서 (문서마다 맞은 조각 최대 2개).
        반환: {"hits": [{id, kind, title, body, chunk_ids, published, road_ids, score, bm25, cosine}],
               "road_filter", "method", "visible", "chunks_scored"}"""
        visible = [i for i, c in enumerate(self.chunks)
                   if self.articles[c["doc"]]["published_s"] <= now_s
                   and (kind is None or self.articles[c["doc"]]["kind"] == kind)]
        want = {str(r) for r in road_ids or []}
        road_filter = "none"
        pool = visible
        if want:
            def related(i):
                a = self.articles[self.chunks[i]["doc"]]
                return bool(want & set(a["road_ids"])) or (a["kind"] == "guide" and not a["road_ids"])
            pool = [i for i in visible if related(i)]
            road_filter = "matched"
            if not any(want & set(self.articles[self.chunks[i]["doc"]]["road_ids"]) for i in pool):
                pool, road_filter = visible, "relaxed"       # 그 도로를 다룬 자료가 없으면 시각만 거른 전체에서
        n_visible_docs = len({self.chunks[i]["doc"] for i in visible})
        if not pool:
            return {"hits": [], "road_filter": road_filter, "method": "none", "visible": n_visible_docs,
                    "chunks_scored": 0}
        q = tokens(query or "")
        bm = np.array([self._bm25(q, i) for i in pool])
        bm_n = bm / bm.max() if bm.max() > 0 else bm
        cos, method, fusion = None, "bm25", "bm25_only"
        if use_embedding and self.embed is not None and query:
            try:
                docs = self.build_index()
                qv = np.asarray(self.embed([query], "RETRIEVAL_QUERY")[0], dtype=float)
                qv = qv / max(np.linalg.norm(qv), 1e-12)
                cos = docs[pool] @ qv
                method, fusion = "bm25+embedding", "rrf"
            except Exception as e:   # noqa: BLE001 — 임베딩이 안 되면 BM25 만
                method = f"bm25 (임베딩 실패: {type(e).__name__})"
        rank_bm = np.empty(len(pool), dtype=int)
        rank_bm[np.argsort(-bm, kind="stable")] = np.arange(1, len(pool) + 1)
        rank_cos = None
        if cos is None:
            score = bm_n
        else:
            rank_cos = np.empty(len(pool), dtype=int)
            rank_cos[np.argsort(-cos, kind="stable")] = np.arange(1, len(pool) + 1)
            # BM25 가 0 (낱말이 하나도 안 겹침) 인 조각은 BM25 목록에 없는 것으로 본다 — 순위 점수를 주지 않는다
            score = np.where(bm > 0, 1.0 / (RRF_K + rank_bm), 0.0) + 1.0 / (RRF_K + rank_cos)
        by_doc: dict[int, list[int]] = {}
        for j in np.argsort(-score, kind="stable"):
            by_doc.setdefault(self.chunks[pool[j]]["doc"], []).append(int(j))
        ranked = sorted(by_doc.items(), key=lambda kv: -score[kv[1][0]])[:k]
        hits = []
        for di, js in ranked:
            a = self.articles[di]
            top = sorted(js[:CHUNKS_PER_DOC], key=lambda j: self.chunks[pool[j]]["chunk_id"])
            best = js[0]
            hits.append({"id": a["id"], "kind": a["kind"], "title": a["title"],
                         "body": " … ".join(self.chunks[pool[j]]["text"] for j in top),
                         "chunk_ids": [self.chunks[pool[j]]["chunk_id"] for j in top],
                         "published": fmt_time(a["published_s"]) if a.get("published") else None,
                         "road_ids": a["road_ids"], "score": round(float(score[best]), 5),
                         "bm25": round(float(bm[best]), 3), "rank_bm25": int(rank_bm[best]),
                         "cosine": None if cos is None else round(float(cos[best]), 3),
                         "rank_cosine": None if rank_cos is None else int(rank_cos[best])})
        return {"hits": hits, "road_filter": road_filter, "method": method, "fusion": fusion,
                "visible": n_visible_docs, "chunks_scored": len(pool)}

    # --- 뉴스 사이트용 조회 (ugv/server.py /news/api) ----------------------------
    def visible_docs(self, now_s: float, kind: str | None = None) -> list[dict]:
        """지금 시각까지 나온 문서 (최신 먼저, 지침은 뒤). 본문 포함."""
        out = [a for a in self.articles if a["published_s"] <= now_s and (kind is None or a["kind"] == kind)]
        return sorted(out, key=lambda a: (a["kind"] != "news", -a["published_s"], a["id"]))

    def doc(self, doc_id: str) -> dict | None:
        return next((a for a in self.articles if a["id"] == doc_id), None)


class NewsApiClient:
    """도로 AI 가 지식 베이스를 웹 API(GET {base}/news/api/search)로 찾게 하는 클라이언트. RoadNews.search 와 같은 모양으로 돌려준다.
    API 가 안 되면(서버 미기동·오류) local(RoadNews) 로 직접 찾고 source 에 사유를 남긴다 — 판단은 멈추지 않는다."""

    def __init__(self, base_url: str, local: "RoadNews | None" = None, timeout_s: float = 5.0, http=None):
        self.base, self.local, self.timeout_s, self._http = base_url.rstrip("/"), local, timeout_s, http

    @property
    def start_kst(self):
        return getattr(self.local, "start_kst", None)

    @property
    def articles(self):
        return getattr(self.local, "articles", [])

    def stats(self) -> dict:
        return {**(self.local.stats() if self.local else {}), "via": f"{self.base}/news/api/search"}

    def search(self, query: str, now_s: float, road_ids: list[str] | None = None, k: int = 3,
               kind: str | None = None, use_embedding: bool = True) -> dict:
        params = {"q": query or "", "now_s": now_s, "k": k}
        if road_ids:
            params["road_ids"] = ",".join(str(r) for r in road_ids)
        if kind:
            params["kind"] = kind
        url = f"{self.base}/news/api/search"
        try:
            if self._http is not None:
                data = self._http(url, params, self.timeout_s)
            else:
                import httpx
                r = httpx.get(url, params=params, timeout=self.timeout_s)
                r.raise_for_status()
                data = r.json()
            return {**data, "source": f"news_api GET /news/api/search"}
        except Exception as e:   # noqa: BLE001 — 웹 API 가 안 되면 내부 검색으로
            if self.local is None:
                raise
            out = self.local.search(query, now_s, road_ids, k=k, kind=kind, use_embedding=use_embedding)
            return {**out, "source": f"local (뉴스 API 실패: {type(e).__name__})"}
