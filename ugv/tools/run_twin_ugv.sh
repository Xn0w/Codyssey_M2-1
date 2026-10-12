#!/usr/bin/env bash
# 작성: AI 코딩 도구(Claude Code)를 사용해 작성·검토한 코드다.
# UGV 트윈 실행 — 세 구성 (공통 문서 5-2)
#   main     팀 main 총괄 동작: UGV 열화상·지상 자동 정찰 끔 → UGV 는 출동하지 않음 (드론 순찰·소방차 방어만)
#   dispatch 시험 구성: 신고 때 총괄이 UGV 도 출동시킴 (25a0183 기본값). 5-3 ⑥·⑦ 통합 시험이 이것
#   final    최종 통합 시나리오: dispatch + 거절 요청 자동 1건 (시뮬레이션 40분, TARGET_UNREACHABLE)
#
#   bash ugv/tools/run_twin_ugv.sh final         # 켜기
#   python run_servers.py stop               # 끄기 (거절 요청 도구는 요청 뒤 스스로 끝남)
# 거절 요청을 손으로 원하는 때에 넣으려면: dispatch 로 켠 뒤 python ugv/tools/twin_reject_request.py
set -e
MODE="${1:-final}"
cd "$(dirname "$0")/../.."
PY="${PY:-}"
for p in .venv/bin/python ../../.venv/bin/python python3; do
  if [ -z "$PY" ] && command -v "$p" >/dev/null 2>&1; then PY="$p"; fi
done
case "$MODE" in
  main)     ORCH_UGV_THERMAL=0 ORCH_AUTO_RECON_GROUND=0 "$PY" run_servers.py start --twin ;;
  dispatch) "$PY" run_servers.py start --twin ;;
  final)
    "$PY" run_servers.py start --twin
    mkdir -p logs
    nohup "$PY" ugv/tools/twin_reject_request.py --auto "${@:2}" > logs/twin_reject_request.log 2>&1 &
    echo "  reject   ✅ 실행    -    거절 시연 요청 (시뮬레이션 40분에 1건, 기록 logs/twin_reject_request.log)  (PID $!)"
    ;;
  *) echo "사용법: $0 main|dispatch|final [twin_reject_request.py 옵션]"; exit 2 ;;
esac
