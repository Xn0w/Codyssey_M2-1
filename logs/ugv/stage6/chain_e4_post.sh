#!/usr/bin/env bash
# chain_e4 끝난 뒤: ULog 덤프(WSL) + e4_judge (chain_e4.sh 는 실행 중이라 수정하지 않고 별도 후처리)
cd "$(dirname "$0")/../../.."
until grep -q "CHAIN_E4_DONE\|CHAIN_E4_HOLD" logs/ugv/stage6/chain_e4.out 2>/dev/null; do sleep 30; done
grep -q CHAIN_E4_HOLD logs/ugv/stage6/chain_e4.out && { echo "CHAIN_E4_POST_SKIP $(date) (E4 보류)"; exit 0; }
O=logs/ugv/stage6/e4; W=/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR/$O
for f in $O/ulog_e4_*.txt; do
  T=$(basename $f .txt); T=${T#ulog_}; U=$(tr -d '\r' < $f | tail -1)
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec python3 $W/e4_ulog_dump.py "$U" $W/ulog_$T.json >> $O/ulog_dump.out 2>&1
done
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe $O/e4_judge.py > $O/e4_judge.out 2>&1
echo "CHAIN_E4_POST_DONE $(date)"; cat $O/e4_judge.out
