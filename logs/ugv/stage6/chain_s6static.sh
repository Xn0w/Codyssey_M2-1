#!/usr/bin/env bash
# 2026-10-13 계획서 S6 정적 단계 (Gazebo 없음) — 대기열이 비어도 다음 단계 진행 (사용자 지시). chain_simint2 뒤 = road_subset 을 쓰는 체인이 모두 끝난 뒤.
# ab_connect (통합 트리): A↔B 지도상 연결·계획기 ACCEPT·정적 기준(종단 10 %·횡단 6 %·2차 차분 0.10 m) — 차종별·방향별. Gazebo 완주는 판정하지 않는다.
# 주의: ab_connect 는 타일 폴더 road_subset_all_included.json 을 다시 쓴다 → 실행 전 백업·해시, 내용이 바뀌면 원본으로 되돌리고 차이를 남긴다.
# 소방차는 통합 트리 profiles(기존 3.8 m) 기준 — fire_v2 기준 확인은 S5 프로필 일치 뒤 다시.
cd "$(dirname "$0")/../../.."
until grep -q CHAIN_SIMINT2_DONE logs/ugv/stage6/chain_simint2.out 2>/dev/null && grep -q CHAIN_E1_DONE logs/ugv/stage6/chain_e1.out 2>/dev/null; do sleep 30; done   # E1 이 같은 road_subset 을 읽으므로 E1 뒤
T=$(pwd)/logs/ugv/stage5/tiles_v2; O=logs/ugv/stage6/s6static; mkdir -p $O
cp $T/road_subset_all_included.json $O/road_subset_all_included.before.json
B=$(sha1sum $T/road_subset_all_included.json | cut -c1-40)
(cd ../ADAIR_wt_integ && git rev-parse HEAD > ../ADAIR/$O/integ_head.txt && PYTHONIOENCODING=utf-8 timeout 3000 ../ADAIR/.venv/Scripts/python.exe -m ugv.tools.ab_connect --tiles $T --out ../ADAIR/$O/ab_connect.json > ../ADAIR/$O/ab_connect.out 2>&1; echo "rc=$?" >> ../ADAIR/$O/ab_connect.out)
A=$(sha1sum $T/road_subset_all_included.json | cut -c1-40)
if [ "$A" != "$B" ]; then
  cp $T/road_subset_all_included.json $O/road_subset_all_included.after.json
  cp $O/road_subset_all_included.before.json $T/road_subset_all_included.json
  echo "road_subset 내용 변경 감지 ($B → $A) — 원본 복원, after 사본 보존" >> $O/ab_connect.out
fi
echo "CHAIN_S6STATIC_DONE $(date) $(tail -1 $O/ab_connect.out)"
