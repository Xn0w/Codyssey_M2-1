#!/usr/bin/env bash
# 시연용 트윈 (feat/demo-ground): run_twin.sh 를 감싸 "시나리오 버튼 = 처음부터 다시 시작" 을 만든다.
#
#   관제판(inje3d LIVE)에서 시나리오 버튼을 누르면 웹이 logs/demo_restart.flag 에 시나리오 id 를 적는다.
#   이 스크립트가 그걸 보고 트윈 전체(환경·UAV·UGV·총괄·웹·시계)를 끄고 새로 띄운 뒤, 불이 확인되면
#   그 시나리오를 자동으로 실행한다 (DEMO_AUTOSTART). 새 로그 폴더 = 차량은 거점에 물 가득, 시계는 14:45.
#   UGV_DRIVER=px4 이면 Gazebo/PX4 도 같이 다시 띄운다 (차 위치·PX4 시계를 맞추려면 필요).
#
#   sim:    ENV_FORECAST_HORIZON_S=14400 ... bash tools/demo_twin.sh          (run_twin.sh 와 같은 환경변수)
#   Gazebo: UGV_DRIVER=px4 UGV_PX4_RESOURCES=F-fire1 ... bash tools/demo_twin.sh
#   끄기:   Ctrl+C
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
FLAG="$ROOT/logs/demo_restart.flag"
mkdir -p "$ROOT/logs"; rm -f "$FLAG"
export DEMO_SUPERVISED=1 DEMO_RESTART_FLAG="$FLAG"
# 물이 떨어진 소방차는 그 자리에 멈춘다 (스스로 복귀하지 않음). 새 출동을 받으면 그때 거점에서 채우고 간다
export UGV_AUTO_RTB_REFILL="${UGV_AUTO_RTB_REFILL:-0}"
export TWIN_ENV_SEED="${TWIN_ENV_SEED-2}"   # LIVE 화재 seed (지금 CA 에서 재현과 비슷하게 자라는 값). 비우면 scenario.json 의 9
export ORCH_LLM_REUSE_SAME_GROUPS="${ORCH_LLM_REUSE_SAME_GROUPS:-1}"   # AI 응답 수 초 사이 근거 수치가 바뀌어도 같은 묶음이면 적용
export UGV_SUPPRESS_RESOURCES="${UGV_SUPPRESS_RESOURCES-F-fire1}"   # 화점 차만 방수, 방어선 소방차는 현장 대기
# Gazebo 모드: 경광등·물줄기 표시 켜기 (ugv/gz_fx.py — 끄면 물은 상태로만 줄고 화면엔 안 보인다)
[[ "${UGV_DRIVER:-sim}" == px4 ]] && export UGV_GZ_FX="${UGV_GZ_FX:-1}"

PORTS="8000 8001 8080 8100 8200 8300"
free_ports(){ for p in $PORTS; do lsof -ti tcp:$p -sTCP:LISTEN 2>/dev/null; done | xargs -r kill 2>/dev/null; sleep 1; }
gazebo(){
  [[ "${UGV_DRIVER:-sim}" == px4 ]] || return 0
  echo "↻ Gazebo/PX4 다시 시작 (${UGV_PX4_RESOURCES:-})"
  ./ugv/tools/px4-stop.sh >/dev/null 2>&1; pkill -f "gz sim" 2>/dev/null; sleep 2
  UGV_FORWARD_ENGINE="${UGV_FORWARD_ENGINE:-1}" GUI="${GUI:-1}" SPEED="${UGV_TIME_SCALE:-4}" \
    ./ugv/tools/px4-start.sh ${UGV_PX4_RESOURCES:-}
}
TWIN=""
stop_twin(){ [[ -n "$TWIN" ]] && kill -TERM "$TWIN" 2>/dev/null && wait "$TWIN" 2>/dev/null; TWIN=""; free_ports; }
trap 'stop_twin; [[ "${UGV_DRIVER:-sim}" == px4 ]] && ./ugv/tools/px4-stop.sh >/dev/null 2>&1; exit 0' INT TERM

SID=""
while true; do
  free_ports
  gazebo
  # 시나리오별 환경 (web/app.py DEMO_SCENARIOS 와 짝)
  #   (선택 전) 출동 없이 불만 번진다 · hq 드론 전진(B), 본부 소방차 · patrol 드론 원통 기지(B′), UGV 대체, 순찰 중 소방차
  case "$SID" in
    ""|idle) SCN=(ORCH_AUTO_RECON=0) ;;
    hq)     SCN=(ORCH_AUTO_RECON=1 TWIN_LAUNCH=forward) ;;
    patrol) SCN=(ORCH_AUTO_RECON=1 TWIN_LAUNCH=base ORCH_AUTO_RECON_GROUND=1 ORCH_UGV_THERMAL=1
                 UGV_EXTRA_UGVS="${UGV_EXTRA_UGVS:-2}" UGV_START_NODES="${UGV_PATROL_START:-A-fire1=495015}") ;;
    *)      SCN=(ORCH_AUTO_RECON=1) ;;
  esac
  [[ "$SID" == idle ]] && SID=""
  echo "▶ 트윈 시작 — ${SID:-출동 없음(불만 번짐)}${SID:+ · 불 확인 뒤 자동 실행} (${SCN[*]})"
  env "${SCN[@]}" DEMO_AUTOSTART="$SID" DEMO_CURRENT="${SID:-idle}" bash tools/run_twin.sh &
  TWIN=$!
  while [[ ! -f "$FLAG" ]] && kill -0 "$TWIN" 2>/dev/null; do sleep 1; done
  if [[ ! -f "$FLAG" ]]; then echo "트윈이 스스로 끝났다 — 종료"; break; fi
  SID="$(tr -dc 'a-z0-9_' < "$FLAG")"; rm -f "$FLAG"
  echo "↻ 시나리오 '$SID' — 처음부터 다시"
  stop_twin
done
