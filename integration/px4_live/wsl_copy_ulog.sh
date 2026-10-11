#!/usr/bin/env bash
# integration/px4_live/wsl_copy_ulog.sh <상태 폴더(홈 기준)> <대상 폴더> — 인스턴스 0·1 의 마지막 ULog 와 PX4 콘솔 로그를 복사
S="$HOME/$1"; D="$2"; mkdir -p "$D"
for i in 0 1; do
  f=$(ls -t "$S"/px4-$i/log/*/*.ulg 2>/dev/null | head -1)
  [ -n "$f" ] && cp "$f" "$D/px4-$i.ulg"
  [ -f "$S/px4-$i.log" ] && cp "$S/px4-$i.log" "$D/"
done
ls -la "$D"
