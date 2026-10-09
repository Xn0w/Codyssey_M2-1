#!/usr/bin/env bash
# 도로 AI 시연 2 — 총괄 요청으로 UGV 두 대 출동, 가는 길이 각각 막힌다 (UGV 담당 시연, 봉인 기능)
#   A-ugv1 (인제119): 설악로 남전리 8분 통제 → 우회 +24분보다 짧아 잠깐 대기 후 원래 길 (기사 N10, 지침 G1)
#   B-ugv1 (기린119): 내린천로 오후 4시까지 통제 → 우회 (+8분) — 대조군 (기사 N11)
# 총괄은 기존 시연 시나리오(orchestrator/tests/scenarios/smoke_ugv_support: 연기로 드론 관측 불가 → UGV 지상 지원)의
# 시험 환경을 그대로 쓴다. 남전리 신고(119)로 총괄이 최초 정찰을 만들고, 지상 지원 임무를 하나 더 보내면
# 총괄이 배정한다 — 최초 정찰은 가장 가까운 A-ugv1, 지상 지원은 남은 B-ugv1 (드론 서버는 띄우지 않는다).
#
#   ugv/tools/demo_agent_dispatch.sh            # 저장소 루트에서. 끄기: Ctrl+C
# 기사 N10·N11 은 ugv/scenarios/agent_dispatch/news/ — UGV_SCENARIO 옆 폴더라 서버가 공통 지식(ugv/knowledge)과 함께 읽는다
# 키: 저장소 루트 .env 의 UGV_AGENT_API_KEY. 배속 UGV_TIME_SCALE (기본 10 — LLM 응답 9초 = 시뮬레이션 1.5분)
# 화면: 상황판 http://localhost:8100/view (도로 AI 탭), 교통 소식 http://localhost:8100/news, 총괄 http://localhost:8200/board,
#       3D http://localhost:8080/inje3d → '실시간 연결 LIVE' (UGV 위치만 — 환경·드론 서버는 이 시연에서 띄우지 않는다)
# tools/run_twin.sh 와 같은 포트(8100·8200·8080)를 쓰므로 동시에 돌리지 않는다.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="${PY:-.venv/bin/python}"; [ -x "$PY" ] || PY=python3
LOG="logs/agent_dispatch/$(date +%Y%m%d_%H%M%S)"; mkdir -p "$LOG"
pkill -f "uvicorn ugv.server:app" 2>/dev/null || true
pkill -f "orchestrator.api" 2>/dev/null || true
pkill -f "uvicorn web.app:app" 2>/dev/null || true
sleep 1
UGV_AGENT=1 UGV_SCENARIO=ugv/scenarios/agent_dispatch.csv UGV_TIME_SCALE="${UGV_TIME_SCALE:-10}" UGV_ENV_URL="" \
  "$PY" -m uvicorn ugv.server:app --host 127.0.0.1 --port 8100 --log-level warning > "$LOG/ugv.log" 2>&1 &
UGV_PID=$!
ORCH_ENV_FIXTURE=orchestrator/tests/scenarios/smoke_ugv_support/fixture.json ORCH_DB_PATH="$LOG/orchestrator.sqlite3" \
  "$PY" -m orchestrator.api > "$LOG/orchestrator.log" 2>&1 &
ORCH_PID=$!
"$PY" -m uvicorn web.app:app --host 127.0.0.1 --port 8080 --log-level warning > "$LOG/web.log" 2>&1 &
WEB_PID=$!
trap 'echo; echo "종료 중…"; kill $UGV_PID $ORCH_PID $WEB_PID 2>/dev/null; wait 2>/dev/null; echo "로그: $LOG"' EXIT INT TERM
for u in http://127.0.0.1:8100/health http://127.0.0.1:8200/health http://127.0.0.1:8080/inje3d; do
  for _ in $(seq 1 60); do curl -s -o /dev/null "$u" && break; sleep 0.5; done
done
echo "▶ 총괄에 지상 지원 임무 (최초 정찰과 함께 배정된다)"
curl -s -X POST http://127.0.0.1:8200/tasks -H "Content-Type: application/json" \
     --data-binary @ugv/scenarios/agent_dispatch/task.json > /dev/null
sleep 1
curl -s http://127.0.0.1:8200/tasks | "$PY" -c 'import json,sys
for t in json.load(sys.stdin): print("  ", t.get("kind"), t.get("purpose_status"))'
curl -s http://127.0.0.1:8100/view/vehicles | "$PY" -c 'import json,sys
for v in json.load(sys.stdin): print("  ", v.get("resource_id"), (v.get("task") or {}).get("task_id") or "대기")'

echo "✔ 상황판 http://localhost:8100/view (도로 AI 탭) · 교통 소식 http://localhost:8100/news · 총괄 http://localhost:8200/board"
echo "  3D   http://localhost:8080/inje3d → '실시간 연결 LIVE' (UGV 위치)"
echo "  끄기: Ctrl+C   로그: $LOG"
wait
