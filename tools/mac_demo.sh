#!/usr/bin/env bash
# Mac 시연 실행 (sim 전용, Gazebo 없음) — feat/demo-ground
#   bash tools/mac_demo.sh          # 4배속
#   bash tools/mac_demo.sh 10       # 10배속
# 종료: Ctrl-C (포트 8000 8001 8080 8100 8200 8300 정리)
# 브라우저: http://localhost:8080/inje3d#live → 왼쪽 아래 시나리오 버튼 (버튼 = 처음부터 다시)
# 사전 준비: 저장소 루트 .env (ORCH_LLM_PROVIDER=gemini, GEMINI_API_KEY, ORCH_LLM_MODEL=gemini-3.8-flash) — 커밋 금지
set -euo pipefail
cd "$(dirname "$0")/.."
SPEED="${1:-${SPEED:-4}}"

[[ -f .env ]] || echo "⚠ .env 없음 — AI 판단이 DISABLED 로 나온다"
[[ -x .venv/bin/python ]] || { echo "✖ .venv 없음 (python3 -m venv .venv && .venv/bin/pip install -r requirements-integrated.txt)"; exit 1; }

export PY="$PWD/.venv/bin/python"
export UGV_DRIVER=sim
export TWIN_OPERATOR=0 TWIN_SPEED="$SPEED" UGV_TIME_SCALE="$SPEED"
export ENV_FORECAST_HORIZON_S=14400 ORCH_ENV_SENSE_TYPES=UAV,UGV
export UGV_FORWARD_ENGINE=1 UGV_DEMO_REAL_SPEED=1

echo "▶ sim ${SPEED}배속 · http://localhost:8080/inje3d#live"
exec bash tools/demo_twin.sh
