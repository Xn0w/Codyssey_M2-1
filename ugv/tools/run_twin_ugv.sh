#!/usr/bin/env bash
# 작성: AI 코딩 도구(Claude Code)를 사용해 작성·검토한 코드다.
# UGV 트윈 실행 — 세 구성 (공통 문서 5-2)
#   main     팀 main 총괄 동작: UGV 열화상·지상 자동 정찰 끔 → UGV 는 출동하지 않음 (드론 순찰·소방차 방어만)
#   dispatch 시험 구성: 신고 때 총괄이 UGV 도 출동시킴 (25a0183 기본값). 5-3 ⑥·⑦ 통합 시험이 이것
#   final    최종 통합 시나리오: dispatch + 거절 요청 자동 1건 (시뮬레이션 40분, TARGET_UNREACHABLE)
#   thermal  UGV 시연: 기존 마을회관 방어 출동(tools/twin_ground_dispatch.py)을 UGV 로 (남전1리 마을회관·인제휴게소)
#            + 불 칸으로 UGV 전용 열화상 요청 자동 (20분부터 30분마다 최대 6건, 2 km 지형 시선 관측)
#   nodrone  드론 출동 불가 시나리오: 드론 서버를 띄우지 않는다 → 신고 때 총괄 자동 정찰(드론·UGV 허용)이
#            드론에 닿지 못하고(LOCAL_UNREACHABLE) 스스로 UGV 를 골라 보낸다. 운용자 요청 없음 (총괄 자체 판단)
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
  thermal)
    TWIN_DISPATCH_ARGS="${TWIN_DISPATCH_ARGS:---types UGV --site NAMJEON1_HALL,INJE_REST_AREA}" "$PY" run_servers.py start --twin
    mkdir -p logs
    nohup "$PY" ugv/tools/twin_thermal_request.py --auto "${@:2}" > logs/twin_thermal_request.log 2>&1 &
    echo "  thermal  ✅ 실행    -    마을회관·휴게소 방어 출동은 UGV 로 + UGV 열화상 요청 (20분부터 30분마다 최대 6건, 기록 logs/twin_thermal_request.log)  (PID $!)"
    ;;
  nodrone)
    "$PY" run_servers.py start --twin env ugv orch web clock operator dispatch
    echo "  nodrone  드론 서버 없음 — 신고 때 총괄 자동 정찰이 UGV 로 가는지 확인: http://127.0.0.1:8200/board"
    ;;
  *) echo "사용법: $0 main|dispatch|final|thermal|nodrone [요청 도구 옵션]"; exit 2 ;;
esac
