#!/usr/bin/env bash
# 접근 위반(rc 139 / 0xC0000005) 진단 재현 1회 — 전체 단위시험 + faulthandler + 환경·프로세스·종료 코드 기록 (2026-10-14)
# 사용: bash run_av_diag.sh <run_id> [extra env e.g. PYTHONMALLOC=debug]
RID=$1; shift
D=/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/logs/ugv/stage6/av_diag/$RID; mkdir -p $D
cd /c/Users/수다쟁이고양이들/Documents/GitHub/${TREE:-ADAIR_wt_integ}
PY=../ADAIR/.venv/Scripts/python.exe
{ echo "run_id $RID"; echo "start $(date -Is)"; echo "tree $(pwd) HEAD $(git rev-parse HEAD) dirty_ugv $(git status --porcelain --untracked-files=no -- ugv | wc -l)"
  echo "python $($PY -c 'import sys;print(sys.executable, sys.version)')"; echo "venv_cfg"; cat ../ADAIR/.venv/pyvenv.cfg
  echo "extra_env $*"; echo "cmd env $* $PY -X faulthandler -m pytest -q ugv/tests"; } > $D/meta.txt 2>&1
$PY -m pip freeze > $D/pip_freeze.txt 2>&1
tasklist //FI "IMAGENAME eq python.exe" //V > $D/procs_start.txt 2>&1
T0=$(date +%s)
env "$@" PYTHONIOENCODING=utf-8 PYTHONFAULTHANDLER=1 $PY -X faulthandler -m pytest -q ugv/tests > $D/pytest.txt 2> $D/pytest.err
RC=$?
{ echo "end $(date -Is)"; echo "elapsed_s $(( $(date +%s) - T0 ))"; echo "rc $RC"; } >> $D/meta.txt
tasklist //FI "IMAGENAME eq python.exe" //V > $D/procs_end.txt 2>&1
echo "AV_DIAG_DONE $RID rc=$RC"
