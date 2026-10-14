#!/usr/bin/env bash
# 2026-10-13 sim 진단 v3 (통합 보완 1~4·7) — Gazebo 시험과 겹치지 않게 chain_s4b 와 chain_ft3 사이. 20회 + 시나리오 B 5회.
# DONE 줄 = '묶음 끝' (성공·유효 아님). 실행 기준 manifest·회차 JSONL(생성 즉시 기록)·B 회차별 원문/종료 코드 보존. 진단 결과로 S5 를 통과시키지 않는다.
cd "$(dirname "$0")/../../../.."
until grep -q CHAIN_S4B_DONE ADAIR/logs/ugv/stage6/chain_s4b.out 2>/dev/null; do sleep 30; done
S6=../ADAIR/logs/ugv/stage6; OUT=$S6/flaky_diag_v3; PY=../ADAIR/.venv/Scripts/python.exe
cd ADAIR_wt_integ && mkdir -p $OUT
# 실행 기준 고정
$PY - > $OUT/manifest.json <<'PYEOF'
import hashlib, json, os, subprocess, sys
sys.path.insert(0, ".")
def sha(p):
    return hashlib.sha1(open(p, "rb").read().replace(b"\r", b"")).hexdigest()
import ugv, orchestrator, ugv.vehicle, ugv.drivers.sim
g = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
print(json.dumps({"tree": os.getcwd(), "head": g("rev-parse", "HEAD"), "ugv_tree_hash": g("rev-parse", "HEAD:ugv"),
                  "orchestrator_tree_hash": g("rev-parse", "HEAD:orchestrator"), "dirty": g("status", "--porcelain", "--untracked-files=no"),
                  "import": {"ugv": ugv.__file__, "orchestrator": orchestrator.__file__, "vehicle": ugv.vehicle.__file__, "sim": ugv.drivers.sim.__file__},
                  "sha1": {f: sha(f) for f in ("../ADAIR/logs/ugv/stage6/flaky_diag.py", "../ADAIR/logs/ugv/stage6/flaky_post.py", "ugv/tests/test_orchestrator_closed_loop.py",
                                               "ugv/vehicle.py", "ugv/drivers/sim.py", "ugv/traffic.py", "ugv/server.py")},
                  "flags": {"UGV_TEST_HOOKS": "1 (시험이 설정)", "scale": 30.0, "TICK_WALL_S": 0.05}, "python": sys.version}, ensure_ascii=False, indent=1))
PYEOF
PYTHONIOENCODING=utf-8 timeout 3600 $PY $S6/flaky_diag.py 20 $OUT > $OUT/diag.out 2>&1
RC=$?
PYTHONIOENCODING=utf-8 timeout 900 $PY $S6/flaky_post.py $OUT > $OUT/post.out 2>&1
PRC=$?
SUM=$(grep DIAG_SUMMARY $OUT/diag.out | tail -1)
NRES=$(ls $OUT/run*.jsonl 2>/dev/null | wc -l)
# 시나리오 B (막는 차 30 m 보간 배치, 305fdd7) 5회 — 회차별 전체 원문·종료 코드
NB=0
for i in 1 2 3 4 5; do
  PYTHONIOENCODING=utf-8 $PY -m pytest -q -p no:cacheprovider "ugv/tests/test_orchestrator_closed_loop.py::test_closed_loop_blocked_vehicle_is_released_not_faulted" > $OUT/simtest_B_$i.txt 2>&1
  rc=$?; echo "rc=$rc" >> $OUT/simtest_B_$i.txt; [ $rc = 0 ] && NB=$((NB+1))
done
echo "CHAIN_SIMDIAG_DONE $(date) diag_rc=$RC post_rc=$PRC run_files=$NRES/20 ${SUM:-DIAG_SUMMARY 없음 (중단·시간 초과)} blocked_test_rc0=$NB/5"
