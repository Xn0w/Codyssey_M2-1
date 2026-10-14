#!/usr/bin/env bash
# 2026-10-13 S3: fire_v2 뒷바퀴 유효 강성 (뒤왼바퀴 아래 2·5 cm 판) — 앞바퀴는 기존 판 시험에서 352·354 kN/m (설정 706 의 0.50).
# 보강한 정적 래퍼(사전·사후 정지·출처 증거) 첫 사용. chain_simdiag(sim 진단) 뒤에.
cd "$(dirname "$0")/../../.."
until grep -q CHAIN_SIMDIAG_DONE logs/ugv/stage6/chain_simdiag.out 2>/dev/null; do sleep 30; done
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 --exec bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle && bash ugv/tools/susp_static_test.sh ../ADAIR/logs/ugv/stage6/susp_static_ft3 fire_v2:adair_flat_diag2ft2r:60:adair_firetruck fire_v2:adair_flat_diag5ft2r:60:adair_firetruck fire_v2:adair_flat_susp:60:adair_firetruck" > logs/ugv/stage6/static_ft3.out 2>&1
echo "CHAIN_FT3_DONE $(date)"
