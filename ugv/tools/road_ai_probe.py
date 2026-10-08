# ugv/tools/road_ai_probe.py — 도로 AI 실제 Gemini 연결 확인 (서버 없이)
#
#   python -m ugv.tools.road_ai_probe                  # function calling(B)
#   python -m ugv.tools.road_ai_probe --mode inline    # 기사를 프롬프트에 넣는 방식(A)
#   python -m ugv.tools.road_ai_probe --no-embed       # 임베딩 없이 BM25 만
# 키: UGV_AGENT_API_KEY (환경변수 또는 저장소 루트 .env). 모델: UGV_AGENT_MODEL (기본 gemini-2.5-flash)
# 시연 시나리오(agent_block.csv)와 같은 상황 — 14:52 설악로 통제(기사 N1: 15:30 해제 예정), 우회 +3분 — 을 넣고
# 모델이 기사를 찾아 무엇을 고르는지, 몇 번 불렀는지, 얼마나 걸렸는지 찍는다.

import argparse
import json
import os
from pathlib import Path

from ugv import config
from ugv.road_ai import GeminiClient, RoadAI, load_env_keys
from ugv.road_news import RoadNews

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=config.AGENT_MODE, choices=["function_calling", "inline"])
    ap.add_argument("--no-embed", action="store_true")
    a = ap.parse_args()
    load_env_keys(ROOT / ".env")
    key = os.getenv("UGV_AGENT_API_KEY")
    if not key:
        raise SystemExit("UGV_AGENT_API_KEY 가 없습니다 (.env 에 UGV_AGENT_API_KEY=... 한 줄)")
    client = GeminiClient(key, os.getenv("UGV_AGENT_MODEL", config.AGENT_MODEL), config.AGENT_EMBED_MODEL,
                          config.AGENT_BASE_URL, config.AGENT_TIMEOUT_S)
    news = RoadNews.load(ROOT / config.AGENT_NEWS, embed=None if a.no_embed else client.embed)
    ai = RoadAI(client, news, a.mode)
    start = 14 * 3600 + 45 * 60
    s = {"now_s": 7 * 60, "now_text": "14:52", "resource_id": "A-ugv1", "resource_type": "UGV",
         "target": "설악로(화점 부근)", "blocked_road_id": "682501434", "blocked_name": "설악로", "here_name": "설악로",
         "eta_before_s": 540,
         "options": [{"name": "ROUTE_1", "eta_s": 720, "distance_m": 1200, "road_ids": ["682501397", "682502600", "682502598"],
                      "road_names": ["설악로", "신상촌길", "설악로"], "path": []},
                     {"name": "ROUTE_2", "eta_s": 760, "distance_m": 1300, "road_ids": ["682502600", "682501898"],
                      "road_names": ["신상촌길"], "path": []}],
         "to_sim": lambda hhmm: int(hhmm[:2]) * 3600 + int(hhmm[3:5]) * 60 - start}
    out = ai.decide(s)
    print(json.dumps({k: v for k, v in out.items() if k != "trace"}, ensure_ascii=False, indent=2))
    for e in out["trace"]:
        e = {k: (v if k != "prompt" else v[:200] + "…") for k, v in e.items()}
        print(json.dumps(e, ensure_ascii=False))
    print(f"LLM 호출 {ai.calls}회, 모드 {a.mode}, 모델 {client.model}")


if __name__ == "__main__":
    main()
