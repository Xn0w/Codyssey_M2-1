#!/usr/bin/env bash
# run_sc_v12 (2026-10-14 전 타일 보정 tiles_v2c1) = v11 + CAND_PAT (prov 후보 dir 문자열, 기본 seamC/tiles_c1)·CAND_NC (기대 개수, 기본 2). 원 설명: run_sc_v11_c1 (2026-10-14 Codex 0940 2절 A) = v10_ops 사본 + CAND_ROOT (WSL 경로) 가 있으면 모델 검색 앞에 후보 루트, 기동 뒤 후보 해석 증거
#   (gz 로그 AABB 반폭 500 = CAND_N500 줄·499.512 = CAND_N499 줄, run_provenance 의 T04_16·T05_16 dir 이 후보 루트) 아니면 invalid_evidence (종료 7). 나머지 동일.
# run_sc_v10_ops (2026-10-14 Codex 0755 2절) = v9 사본, 서버 기동의 UGV_TEST_HOOKS 만 0 (운영 park 1.0 s·시험 endpoint 없음). 나머지 동일.
# run_sc_v9 (2026-10-14 진단 7) = v8 + GZ_REC_MODEL 이면 시험 동안 gz 기록기 (logs/ugv/stage6/diag7/gz_rec.py).
# run_sc_v8 (2026-10-14 Codex 0155 3절) = v7 + Windows 서버 기동 환경에도 ADAIR_RUN_ID=<TAG> (park_events run_id 연결).
# run_sc_v7.sh (2026-10-14) = run_sc_v6.sh + 단계별 종료 코드 rc_<TAG>.json (test·copy_logs·stop_post·invalid_stop), 스크립트 rc = 시험 rc(0 이면 사후 정지 무효 시 8), 같은 TAG 재사용 거부(9).
# run_sc_v6 (2026-10-13) = run_sc_v5 + WSL 호출을 `wsl.exe --exec` 로 (v5 의 `wsl.exe -- bash -lc "...; echo rc=$?"` 는 WSL 기본 셸이 $? 를 먼저 확장해 rc 가 WSL 안 종료 코드가 아니었다 — 사후 rc=0 검사 무효, JSON 잔존 검사만 유효).
# run_sc_v5 (2026-10-12, 차량 개조 진행 독립 검증 반영): run_sc_v4 기반.
#  - 서버 작업 트리 SERVER_TREE (기본 ADAIR_wt_turn). 정체 감지(UGV_PX4_STALL_DETECT)·MISSION_STALL 은 ADAIR_wt_fix 에만 있다 → 그 시험은 SERVER_TREE=ADAIR_wt_fix.
#    서버 기동 전에 같은 환경으로 import 경로·커밋·STALL_DETECT/PASS_SKIP 실제 값을 server_evidence_<TAG>.json 에 남긴다.
#  - 정지 → 결과(stop_last.json) 검사 → 깨끗할 때만 기동. 앞 실행 잔존(residual_own/still_alive > 0)이면 시험 안 함(종료 5, <TAG>.contaminated).
#    기동이 CONTAMINATED(앞 실행 월드·PX4 재사용 거부)면 시험 안 함(종료 6).
#  - 실제 해석 증거: prov_<TAG>.json (ugv/tools/run_provenance.py — 이 실행 ID 의 PX4 프로세스 환경의 모델 경로를 Gazebo 해석 순서로 따라가 차종별 model.sdf·월드 해시).
#  - 증거 검사(verify_evidence.py): 기대 서버 플래그·모델 해시·Gazebo 서스펜션 관절·타일 해시 — 어긋나면 시험 안 함(종료 7, <TAG>.invalid_evidence).
#  - 사후 정지: 종료 코드와 stop_post JSON 을 읽어 실패·잔존·기록 누락이면 <TAG>.invalid_stop (무효 분류용). 체인 DONE 은 '체인 끝'일 뿐 '모든 회차 유효'가 아니다.
# run_sc_v4 = run_sc_v3 + manifest 모델 해석 수정 (v3 는 resolved_model 이 빈 값 해시로 남는 결함). run_sc_v3 (2026-10-12 차량 개조 검증): run_sc_v2 사본 + WSL 기동·종료는 ../ADAIR_wt_vehicle 의 px4-start/stop (프로세스 기록·실행 오염 거부),
#   차량 후보 UGV_MODEL_VARIANT=<후보> (ugv/gazebo/variants), 회차마다 manifest_<TAG>.json (코드 커밋·후보 모델 내용 해시·환경), 종료 결과 stop_pre/post_<TAG>.json,
#   앞 실행 잔존·재사용 거부 시 <TAG>.contaminated (무효 분류용). 서버·시험 도구·타일 경로는 v2 와 같다.
# 트윈 지도 정제 v2 시험 월드 (TILES=tiles_v2 기본, 서버 = ../$SRV, EXTRA 가 있으면 시험 전용 덧붙임 도로)
# WORLD=tz_a33 bash logs/ugv/stage4/run_sc_tz.sh <tag> <spawn> <fleet> <command...>   (추가 서버 환경변수는 그대로 전달)
# 무화재 시험 명시 (환경 서버 UGV_ENV_URL 을 주면 그 자료 상태를 쓴다)
export UGV_ALLOW_NO_FIRE_DATA=${UGV_ALLOW_NO_FIRE_DATA:-1}
cd "$(dirname "$0")/../../.."
TAG=$1; SPAWN=$2; FLEET=$3; shift 3
# v7/flat_ab2 (2026-10-14 Codex 지적): 같은 TAG 재사용 거부 — 재시도는 새 TAG (앞 시도의 stop_pre·prov·manifest 를 덮지 않게)
if [ -e "logs/ugv/stage4/manifest_$TAG.json" ] || [ -e "logs/ugv/stage4/$TAG.out" ] && [ "${ALLOW_TAG_REUSE:-0}" != 1 ]; then echo "$TAG 이미 쓴 실행 ID — 새 TAG 로 (ALLOW_TAG_REUSE=1 로만 재사용)"; exit 9; fi
rm -rf "logs/ugv/stage4/state_$TAG"     # 같은 이름 이전 실행의 상태(임무 기록)가 섞이지 않게
M=$(pwd)
R=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR
V=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle
SRV=${SERVER_TREE:-ADAIR_wt_turn}
rm -f logs/ugv/stage4/$TAG.contaminated logs/ugv/stage4/$TAG.invalid_stop logs/ugv/stage4/$TAG.invalid_evidence logs/ugv/stage4/server_evidence_$TAG.json
W=${WORLD:?WORLD 필요}
P=$(netstat -ano -p TCP | awk '$2 ~ /:8100$/ && $4=="LISTENING" {print $5}' | head -1); [ -n "$P" ] && taskkill //F //T //PID $P >/dev/null 2>&1
# 실행 전 검사 (확정적 설정 오류: 타일 누락·생성 높이·공터 잘림·부분집합 불일치 → 재시도 없이 중단)
TD=$M/logs/ugv/stage5/${TILES:-tiles_v2}
( cd ../$SRV && PYTHONIOENCODING=utf-8 UGV_ALLOW_NO_FIRE_DATA=1 ../ADAIR/.venv/Scripts/python.exe -m ugv.tools.world_preflight --world-sdf $TD/$W.sdf --tiles $TD --spawn $M/$SPAWN     $( [ "${PF_SKIP_SUBSET:-0}" = 1 ] || echo "--subset ${SUBSET:-$TD/road_subset_$W.json} ${SUBSET:+--subset-any-world}" ) ${FLAT_Z:+--flat-ground-z $FLAT_Z} ${EXTRA:+--extra $M/logs/ugv/stage5/turn/${EXTRA}_extra_roads.json} --out $M/logs/ugv/stage4/preflight_$TAG.json ) > logs/ugv/stage4/preflight_$TAG.txt 2>&1
if [ $? -ne 0 ]; then echo "$TAG 실행 전 검사 실패 — 시험 안 함: $(grep -a PREFLIGHT logs/ugv/stage4/preflight_$TAG.txt)" | tee logs/ugv/stage4/$TAG.out; exit 3; fi
T0=$(date +%s)
# 1) 정지 → 결과 검사 (깨끗할 때만 기동)
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd $V && STOP_STRICT=1 bash ugv/tools/px4-stop.sh --params >/dev/null; echo rc=\$?; cat ~/.adair-ugv/stop_last.json" > logs/ugv/stage4/stop_pre_$TAG.txt 2>&1
tr -d '\r' < logs/ugv/stage4/stop_pre_$TAG.txt | grep '^{' > logs/ugv/stage4/stop_pre_$TAG.json
if ! grep -q '"residual_own":0,"still_alive":0' logs/ugv/stage4/stop_pre_$TAG.json; then
  echo "앞 실행 잔존 — 시험 안 함: $(cat logs/ugv/stage4/stop_pre_$TAG.txt | tr -d '\r' | paste -sd' ')" | tee logs/ugv/stage4/$TAG.contaminated logs/ugv/stage4/$TAG.out; exit 5
fi
# 2) 기동 (실행 ID = TAG — 다른 실행의 월드·PX4 재사용은 px4-start 가 거부)
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd $V && ADAIR_RUN_ID=$TAG UGV_MODEL_VARIANT=${UGV_MODEL_VARIANT:-} GZ_MODEL_OVERRIDE=${GZ_MODEL_OVERRIDE:-} WORLD=$W WORLD_FILE=$R/logs/ugv/stage5/${TILES:-tiles_v2}/$W.sdf GZ_SIM_RESOURCE_PATH=${CAND_ROOT:+$CAND_ROOT:}$R/logs/ugv/stage5/${TILES:-tiles_v2} bash ugv/tools/wsl_start_fleet.sh $R/$SPAWN" > logs/ugv/stage4/start_$TAG.txt 2>&1
grep MAVLink logs/ugv/stage4/start_$TAG.txt
if grep -q CONTAMINATED logs/ugv/stage4/start_$TAG.txt; then
  echo "기동 거부(실행 오염) — 시험 안 함: $(grep -o 'CONTAMINATED.*' logs/ugv/stage4/start_$TAG.txt | head -1)" | tee logs/ugv/stage4/$TAG.contaminated logs/ugv/stage4/$TAG.out
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd $V && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"; exit 6
fi
# 3) 실제 해석 증거 (이 실행 ID 의 프로세스만)
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --cd "$V" --exec python3 -m ugv.tools.run_provenance --run-id "$TAG" --spawn "$R/$SPAWN" --out "$R/logs/ugv/stage4/prov_$TAG.json" > logs/ugv/stage4/prov_$TAG.txt 2>&1
G=..
printf '{"tag":"%s","server_tree":"%s","server":"%s","tool":"%s","vehicle_tree":"%s","variant":"%s","gz_model_override":"%s","provenance":"prov_%s.json","provenance_status":"%s","tiles":"%s","world":"%s","env":"PASS_SKIP=%s STALL_DETECT=%s LAT_ACCEL=%s","time":"%s"}
'   "$TAG" "$SRV" "$(git -C $G/$SRV rev-parse --short HEAD)$(git -C $G/$SRV status --porcelain | grep -qv '^??' && echo -dirty)"   "$(git -C $G/ADAIR_wt_fix rev-parse --short HEAD)$(git -C $G/ADAIR_wt_fix status --porcelain | grep -qv '^??' && echo -dirty)"   "$(git -C $G/ADAIR_wt_vehicle rev-parse --short HEAD)" "${UGV_MODEL_VARIANT:-}" "${GZ_MODEL_OVERRIDE:-}" "$TAG" "$(tr -d '\r' < logs/ugv/stage4/prov_$TAG.txt | tail -1)" "${TILES:-tiles_v2}" "$W"   "${UGV_PX4_PASS_SKIP:-unset}" "${UGV_PX4_STALL_DETECT:-unset}" "${UGV_LAT_ACCEL:-unset}" "$(date -Is)" > logs/ugv/stage4/manifest_$TAG.json
# 3b) (v11) 후보 해석 증거
if [ -n "${CAND_ROOT:-}" ]; then
  sleep 3
  N500=$(MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "grep -cE 'Heightfield AABB: min = \{-500(\.0+)?, -500(\.0+)?,' \$HOME/.adair-ugv/gz-server.log" | tr -d '
')
  N499=$(MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "grep -cE 'Heightfield AABB: min = \{-499\.512, -499\.512,' \$HOME/.adair-ugv/gz-server.log" | tr -d '
')
  NC=$(../ADAIR/.venv/Scripts/python.exe -c "import json,sys;p=json.load(open(sys.argv[1],encoding='utf-8'));print(sum(1 for t in p['world']['tiles'] if sys.argv[2] in t['dir']))" logs/ugv/stage4/prov_$TAG.json "${CAND_PAT:-seamC/tiles_c1}" 2>/dev/null || echo 0)
  echo "{\"aabb_500\":$N500,\"aabb_499_512\":$N499,\"prov_candidate_tiles\":$NC}" > logs/ugv/stage4/aabb_$TAG.json
  if [ "$N500" != "${CAND_N500:-2}" ] || [ "$N499" != "${CAND_N499:-158}" ] || [ "$NC" != "${CAND_NC:-2}" ]; then
    echo "후보 해석 증거 실패 — 시험 안 함: $(cat logs/ugv/stage4/aabb_$TAG.json)" | tee logs/ugv/stage4/$TAG.invalid_evidence logs/ugv/stage4/$TAG.out
    MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd $V && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"; exit 7
  fi
fi
# 4) 서버 기능 증거: 서버와 같은 작업 트리·환경에서 실제 import 되는 드라이버 모듈과 플래그 값
( cd ../$SRV && PYTHONIOENCODING=utf-8 ../ADAIR/.venv/Scripts/python.exe -c "
import json, ugv.drivers.px4 as p, ugv.vehicle as v
print(json.dumps({'px4_module': p.__file__, 'vehicle_module': v.__file__, 'STALL_DETECT': getattr(p, 'STALL_DETECT', None),
                  'PASS_SKIP': getattr(p, 'PASS_SKIP', None), 'has_MISSION_STALL': 'MISSION_STALL' in open(v.__file__, encoding='utf-8').read(),
                  'candidates': {k: getattr(v, k, None) for k in ('STOP_SPEED_CMD', 'STOP_GRADE_MODE', 'SPEED_TERRAIN_CMD', 'STOP_CAP_FIRST', 'END_EXTEND', 'BLOCK_AVOID_MODE')},
                  'terrain_speed': (lambda T: {k: getattr(T, k) for k in dir(T) if k.isupper() and isinstance(getattr(T, k), (int, float, str, bool))})(__import__('ugv.terrain_speed', fromlist=['x'])) if __import__('importlib.util', fromlist=['x']).find_spec('ugv.terrain_speed') else None,
                  'terrain_tiles_env': __import__('os').getenv('UGV_TERRAIN_TILES')}, ensure_ascii=False))" ) > logs/ugv/stage4/server_evidence_$TAG.json 2>&1
# 5) 증거 검사 — 기대 서버 플래그·모델 해시·Gazebo 서스펜션 관절·타일 해시. 어긋나면 시험 안 함 (종료 7)
if ! PYTHONIOENCODING=utf-8 SERVER_TREE=$SRV ../ADAIR/.venv/Scripts/python.exe logs/ugv/stage4/verify_evidence.py $TAG > logs/ugv/stage4/verify_$TAG.txt 2>&1; then
  echo "증거 검사 실패 — 시험 안 함: $(cat logs/ugv/stage4/verify_$TAG.txt)" | tee logs/ugv/stage4/$TAG.invalid_evidence logs/ugv/stage4/$TAG.out
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd $V && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"; exit 7
fi
echo "$TAG gz+px4 기동 $(( $(date +%s) - T0 )) s" >> logs/ugv/stage4/tz_startup.txt
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "ps -o rss=,vsz=,cmd= -C gz | head -3; free -m | head -2" >> logs/ugv/stage4/tz_startup.txt 2>&1
sleep ${PRE_WAIT:-0}   # 큰 월드는 gz 센서·EKF 준비가 늦다 (PX4 위치 대기 10 s 초과 → PX4_NO_POSITION)
N=$(grep -c . $SPAWN); OK=0
for TRY in 1 2 3; do
  cd ../$SRV
  ADAIR_RUN_ID=$TAG UGV_TEST_HOOKS=0 UGV_VEHICLES_JSON=$M/$FLEET UGV_DRIVER=px4 UGV_STATE_DIR="$M/logs/ugv/stage4/state_$TAG" UGV_ROAD_SUBSET="${SUBSET:-$M/logs/ugv/stage5/${TILES:-tiles_v2}/road_subset_$W.json}" UGV_EXTRA_ROADS="${EXTRA:+$M/logs/ugv/stage5/turn/${EXTRA}_extra_roads.json}"     PYTHONIOENCODING=utf-8 ../ADAIR/.venv/Scripts/python.exe -m uvicorn ugv.server:app --host 127.0.0.1 --port 8100 > $M/logs/ugv/stage4/server_${TAG}_try$TRY.log 2>&1 &
  SP=$!
  cd "$M"
  T1=$(date +%s)
  while kill -0 $SP 2>/dev/null && [ $(( $(date +%s) - T1 )) -lt 180 ]; do
    [ "$(curl -s -H 'X-ADAIR-Monitor: 1' http://127.0.0.1:8100/ugv 2>/dev/null | grep -o '"state":"READY"' | wc -l)" -ge "$N" ] && { OK=1; break; }
    sleep 2
  done
  [ $OK = 1 ] && break
  echo "$TAG 서버 준비 실패 (시도 $TRY) — 20 s 뒤 재시도" >> logs/ugv/stage4/tz_startup.txt
  kill -0 $SP 2>/dev/null && taskkill //F //T //PID "$(cat /proc/$SP/winpid)" >/dev/null 2>&1
  sleep 20
done
cp logs/ugv/stage4/server_${TAG}_try$TRY.log logs/ugv/stage4/server_$TAG.log
# 서버 준비 뒤: PX4 가 보고한 위치가 생성 지점 2 m 안인가 (낙하·엉뚱한 위치 생성 확인)
if [ $OK = 1 ]; then
  curl -s -H 'X-ADAIR-Monitor: 1' http://127.0.0.1:8100/ugv > logs/ugv/stage4/ready_$TAG.json
  ( cd ../$SRV && PYTHONIOENCODING=utf-8 ../ADAIR/.venv/Scripts/python.exe -c "
import json,math,sys
from ugv.geo import FRAME
st={v['resource_id']:v['position'] for v in json.load(open(sys.argv[1],encoding='utf-8'))}
bad=[]
for l in open(sys.argv[2],encoding='utf-8'):
    p=l.split()
    if len(p)<4: continue
    x,y=map(float,p[2].split(',')[:2]); q=st.get(p[3]) or {}
    d=math.inf if q.get('lat') is None else math.dist((x,y),FRAME.to_xy(q['lat'],q['lon']))
    print(p[3],'생성 지점과 PX4 위치 차',round(d,2),'m')
    if d>2.0: bad.append(p[3])
sys.exit(2 if bad else 0)" $M/logs/ugv/stage4/ready_$TAG.json $M/$SPAWN ) >> logs/ugv/stage4/preflight_$TAG.txt 2>&1 || OK=2
fi
[ $OK = 2 ] && { echo "$TAG PX4 위치가 생성 지점과 다름 — 시험 안 함: $(tail -2 logs/ugv/stage4/preflight_$TAG.txt | paste -sd' ')" | tee logs/ugv/stage4/$TAG.out; taskkill //F //T //PID "$(cat /proc/$SP/winpid)" >/dev/null 2>&1; MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd $V && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"; exit 4; }
[ $OK = 1 ] || { echo "$TAG 서버 준비 3회 실패 — 시험 안 함" | tee logs/ugv/stage4/$TAG.out; MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd $V && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"; exit 1; }
# v9 진단 기록 (Codex 0540): GZ_REC_MODEL 이 있으면 시험 동안 WSL gz 기록기 (sim stamp 보존), 끝나면 SIGTERM
if [ -n "${GZ_REC_MODEL:-}" ]; then
  RD=$R/logs/ugv/stage6/diag7/gzrec_$TAG
  # 2026-10-14 수정: bash -lc + 맨 & 는 wsl.exe 세션이 끝나며 기록기가 같이 사라졌다 (d7_flat_s0547_a 기록 없음) → 서브셸·setsid·stdin /dev/null
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "export GZ_PARTITION=adair_ugv; (setsid nohup python3 $R/logs/ugv/stage6/diag7/gz_rec.py --world $W --model $GZ_REC_MODEL --out $RD --duration 600 > $RD.log 2>&1 < /dev/null & echo \$! > /tmp/gzrec_$TAG.pid); sleep 1; ps -p \$(cat /tmp/gzrec_$TAG.pid) -o pid= > /dev/null && echo GZREC_STARTED || echo GZREC_NOT_RUNNING" >> logs/ugv/stage4/start_$TAG.txt 2>&1
  sleep 2
fi
UGV_GZ_WORLD=$W PYTHONIOENCODING=utf-8 "$@" > logs/ugv/stage4/$TAG.out 2>&1
TEST_RC=$?
if [ -n "${GZ_REC_MODEL:-}" ]; then MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -c "kill -TERM \$(cat /tmp/gzrec_$TAG.pid) 2>/dev/null; sleep 3"; fi
taskkill //F //T //PID "$(cat /proc/$SP/winpid)" >/dev/null 2>&1; sleep 2
P=$(netstat -ano -p TCP | awk '$2 ~ /:8100$/ && $4=="LISTENING" {print $5}' | head -1); [ -n "$P" ] && taskkill //F //T //PID $P >/dev/null 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash $R/logs/ugv/stage4/wsl_copy_logs.sh $R/logs/ugv/stage4 $TAG
COPY_RC=$?
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd $V && STOP_STRICT=1 bash ugv/tools/px4-stop.sh >/dev/null; echo rc=\$?; cat ~/.adair-ugv/stop_last.json" > logs/ugv/stage4/stop_post_$TAG.txt 2>&1
tr -d '\r' < logs/ugv/stage4/stop_post_$TAG.txt | grep '^{' > logs/ugv/stage4/stop_post_$TAG.json
if ! grep -q '^rc=0' <(tr -d '\r' < logs/ugv/stage4/stop_post_$TAG.txt) || ! grep -q '"still_alive":0' logs/ugv/stage4/stop_post_$TAG.json || ! grep -q '"residual_own":0' logs/ugv/stage4/stop_post_$TAG.json; then
  echo "사후 종료 확인 실패: $(tr -d '\r' < logs/ugv/stage4/stop_post_$TAG.txt | paste -sd' ')" > logs/ugv/stage4/$TAG.invalid_stop
fi
grep "기록:" logs/ugv/stage4/$TAG.out || true
# 단계별 종료 코드 보존 (v6 는 마지막 grep 의 rc 가 스크립트 rc 가 됐다 — flat_ab1 rc=1 은 시험 실패가 아니었음)
STOP_RC=$(tr -d '
' < logs/ugv/stage4/stop_post_$TAG.txt | grep -o '^rc=[0-9]*' | head -1 | cut -d= -f2)
printf '{"tag":"%s","test_rc":%s,"copy_logs_rc":%s,"stop_post_rc":"%s","invalid_stop":%s,"time":"%s"}
' "$TAG" "$TEST_RC" "$COPY_RC" "${STOP_RC:-unknown}" "$([ -e logs/ugv/stage4/$TAG.invalid_stop ] && echo true || echo false)" "$(date -Is)" > logs/ugv/stage4/rc_$TAG.json
cat logs/ugv/stage4/rc_$TAG.json
[ "$TEST_RC" != 0 ] && exit $TEST_RC
[ -e logs/ugv/stage4/$TAG.invalid_stop ] && exit 8
exit 0
