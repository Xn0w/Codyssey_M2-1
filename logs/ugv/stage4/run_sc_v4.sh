#!/usr/bin/env bash
# run_sc_v4 = run_sc_v3 + manifest 모델 해석 수정 (v3 는 resolved_model 이 빈 값 해시로 남는 결함). run_sc_v3 (2026-10-12 차량 개조 검증): run_sc_v2 사본 + WSL 기동·종료는 ../ADAIR_wt_vehicle 의 px4-start/stop (프로세스 기록·실행 오염 거부),
#   차량 후보 UGV_MODEL_VARIANT=<후보> (ugv/gazebo/variants), 회차마다 manifest_<TAG>.json (코드 커밋·후보 모델 내용 해시·환경), 종료 결과 stop_pre/post_<TAG>.json,
#   앞 실행 잔존·재사용 거부 시 <TAG>.contaminated (무효 분류용). 서버·시험 도구·타일 경로는 v2 와 같다.
# 트윈 지도 정제 v2 시험 월드 (TILES=tiles_v2 기본, 서버 = ../ADAIR_wt_turn, EXTRA 가 있으면 시험 전용 덧붙임 도로)
# WORLD=tz_a33 bash logs/ugv/stage4/run_sc_tz.sh <tag> <spawn> <fleet> <command...>   (추가 서버 환경변수는 그대로 전달)
# 무화재 시험 명시 (환경 서버 UGV_ENV_URL 을 주면 그 자료 상태를 쓴다)
export UGV_ALLOW_NO_FIRE_DATA=${UGV_ALLOW_NO_FIRE_DATA:-1}
cd "$(dirname "$0")/../../.."
TAG=$1; SPAWN=$2; FLEET=$3; shift 3
rm -rf "logs/ugv/stage4/state_$TAG"     # 같은 이름 이전 실행의 상태(임무 기록)가 섞이지 않게
M=$(pwd)
R=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR
V=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle
rm -f logs/ugv/stage4/$TAG.contaminated
W=${WORLD:?WORLD 필요}
P=$(netstat -ano -p TCP | awk '$2 ~ /:8100$/ && $4=="LISTENING" {print $5}' | head -1); [ -n "$P" ] && taskkill //F //T //PID $P >/dev/null 2>&1
# 실행 전 검사 (확정적 설정 오류: 타일 누락·생성 높이·공터 잘림·부분집합 불일치 → 재시도 없이 중단)
TD=$M/logs/ugv/stage5/${TILES:-tiles_v2}
( cd ../ADAIR_wt_turn && PYTHONIOENCODING=utf-8 UGV_ALLOW_NO_FIRE_DATA=1 ../ADAIR/.venv/Scripts/python.exe -m ugv.tools.world_preflight --world-sdf $TD/$W.sdf --tiles $TD --spawn $M/$SPAWN     $( [ "${PF_SKIP_SUBSET:-0}" = 1 ] || echo "--subset ${SUBSET:-$TD/road_subset_$W.json} ${SUBSET:+--subset-any-world}" ) ${FLAT_Z:+--flat-ground-z $FLAT_Z} ${EXTRA:+--extra $M/logs/ugv/stage5/turn/${EXTRA}_extra_roads.json} --out $M/logs/ugv/stage4/preflight_$TAG.json ) > logs/ugv/stage4/preflight_$TAG.txt 2>&1
if [ $? -ne 0 ]; then echo "$TAG 실행 전 검사 실패 — 시험 안 함: $(grep -a PREFLIGHT logs/ugv/stage4/preflight_$TAG.txt)" | tee logs/ugv/stage4/$TAG.out; exit 3; fi
T0=$(date +%s)
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd $V && STOP_STRICT=1 bash ugv/tools/px4-stop.sh --params >/dev/null; echo \$? > /tmp/adair_stop_rc; cp ~/.adair-ugv/stop_last.json $R/logs/ugv/stage4/stop_pre_$TAG.json; ADAIR_RUN_ID=$TAG UGV_MODEL_VARIANT=${UGV_MODEL_VARIANT:-} GZ_MODEL_OVERRIDE=${GZ_MODEL_OVERRIDE:-} WORLD=$W WORLD_FILE=$R/logs/ugv/stage5/${TILES:-tiles_v2}/$W.sdf GZ_SIM_RESOURCE_PATH=$R/logs/ugv/stage5/${TILES:-tiles_v2} bash ugv/tools/wsl_start_fleet.sh $R/$SPAWN" > logs/ugv/stage4/start_$TAG.txt 2>&1
grep MAVLink logs/ugv/stage4/start_$TAG.txt
SRC=$(MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- cat /tmp/adair_stop_rc 2>/dev/null | tr -d '\r')
if grep -q CONTAMINATED logs/ugv/stage4/start_$TAG.txt || [ "$SRC" = 2 ] || [ "$SRC" = 3 ]; then
  echo "앞 실행 잔존 정리 코드 $SRC / 기동 $(grep -o 'CONTAMINATED.*' logs/ugv/stage4/start_$TAG.txt | head -1)" > logs/ugv/stage4/$TAG.contaminated
fi
# 회차 기록: 코드 커밋·후보 모델 내용 해시·환경 (지시서 1절 4항). v4: 해석된 모델 = 실행 중 PX4 의 GZ_SIM_RESOURCE_PATH 첫 항목, 해시는 Windows 쪽 파일 내용(줄바꿈 정규화)
RES=$(MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "p=\$(pgrep -f 'bin/px4 -i' | head -1); tr '\0' '\n' < /proc/\$p/environ | sed -n 's/^GZ_SIM_RESOURCE_PATH=//p' | cut -d: -f1" 2>/dev/null | tr -d '\r')
if [ -n "${UGV_MODEL_VARIANT:-}" ]; then MF=../ADAIR_wt_vehicle/ugv/gazebo/variants/$UGV_MODEL_VARIANT/adair_ugv/model.sdf
elif [ -n "${GZ_MODEL_OVERRIDE:-}" ]; then MF=$(echo "$GZ_MODEL_OVERRIDE" | sed 's#^/mnt/c/#C:/#')/adair_ugv/model.sdf
else MF=../ADAIR_wt_vehicle/ugv/gazebo/models/adair_ugv/model.sdf; fi
MSHA=$( [ -f "$MF" ] && tr -d '\r' < "$MF" | sha1sum | cut -c1-16 || echo missing)
G=..
printf '{"tag":"%s","server":"%s","tool":"%s","vehicle_tree":"%s","variant":"%s","gz_model_override":"%s","model_file":"%s","model_content_sha1":"%s","px4_resource_path_first":"%s","tiles":"%s","world":"%s","env":"PASS_SKIP=%s STALL_DETECT=%s LAT_ACCEL=%s","time":"%s"}
'   "$TAG" "$(git -C $G/ADAIR_wt_turn rev-parse --short HEAD)$(git -C $G/ADAIR_wt_turn status --porcelain | grep -qv '^??' && echo -dirty)"   "$(git -C $G/ADAIR_wt_fix rev-parse --short HEAD)$(git -C $G/ADAIR_wt_fix status --porcelain | grep -qv '^??' && echo -dirty)"   "$(git -C $G/ADAIR_wt_vehicle rev-parse --short HEAD)" "${UGV_MODEL_VARIANT:-}" "${GZ_MODEL_OVERRIDE:-}" "$MF" "$MSHA" "$RES" "${TILES:-tiles_v2}" "$W"   "${UGV_PX4_PASS_SKIP:-unset}" "${UGV_PX4_STALL_DETECT:-unset}" "${UGV_LAT_ACCEL:-unset}" "$(date -Is)" > logs/ugv/stage4/manifest_$TAG.json
echo "$TAG gz+px4 기동 $(( $(date +%s) - T0 )) s" >> logs/ugv/stage4/tz_startup.txt
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "ps -o rss=,vsz=,cmd= -C gz | head -3; free -m | head -2" >> logs/ugv/stage4/tz_startup.txt 2>&1
sleep ${PRE_WAIT:-0}   # 큰 월드는 gz 센서·EKF 준비가 늦다 (PX4 위치 대기 10 s 초과 → PX4_NO_POSITION)
N=$(grep -c . $SPAWN); OK=0
for TRY in 1 2 3; do
  cd ../ADAIR_wt_turn
  UGV_TEST_HOOKS=1 UGV_VEHICLES_JSON=$M/$FLEET UGV_DRIVER=px4 UGV_STATE_DIR="$M/logs/ugv/stage4/state_$TAG" UGV_ROAD_SUBSET="${SUBSET:-$M/logs/ugv/stage5/${TILES:-tiles_v2}/road_subset_$W.json}" UGV_EXTRA_ROADS="${EXTRA:+$M/logs/ugv/stage5/turn/${EXTRA}_extra_roads.json}"     PYTHONIOENCODING=utf-8 ../ADAIR/.venv/Scripts/python.exe -m uvicorn ugv.server:app --host 127.0.0.1 --port 8100 > $M/logs/ugv/stage4/server_${TAG}_try$TRY.log 2>&1 &
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
  ( cd ../ADAIR_wt_turn && PYTHONIOENCODING=utf-8 ../ADAIR/.venv/Scripts/python.exe -c "
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
[ $OK = 2 ] && { echo "$TAG PX4 위치가 생성 지점과 다름 — 시험 안 함: $(tail -2 logs/ugv/stage4/preflight_$TAG.txt | paste -sd' ')" | tee logs/ugv/stage4/$TAG.out; taskkill //F //T //PID "$(cat /proc/$SP/winpid)" >/dev/null 2>&1; MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd $V && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"; exit 4; }
[ $OK = 1 ] || { echo "$TAG 서버 준비 3회 실패 — 시험 안 함" | tee logs/ugv/stage4/$TAG.out; MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd $V && bash ugv/tools/px4-stop.sh >/dev/null 2>&1"; exit 1; }
UGV_GZ_WORLD=$W PYTHONIOENCODING=utf-8 "$@" > logs/ugv/stage4/$TAG.out 2>&1
taskkill //F //T //PID "$(cat /proc/$SP/winpid)" >/dev/null 2>&1; sleep 2
P=$(netstat -ano -p TCP | awk '$2 ~ /:8100$/ && $4=="LISTENING" {print $5}' | head -1); [ -n "$P" ] && taskkill //F //T //PID $P >/dev/null 2>&1
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash $R/logs/ugv/stage4/wsl_copy_logs.sh $R/logs/ugv/stage4 $TAG
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd $V && STOP_STRICT=1 bash ugv/tools/px4-stop.sh >/dev/null; cp ~/.adair-ugv/stop_last.json $R/logs/ugv/stage4/stop_post_$TAG.json"
grep "기록:" logs/ugv/stage4/$TAG.out
