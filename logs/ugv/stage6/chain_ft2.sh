#!/usr/bin/env bash
# 2026-10-12 후속 계획 S3: 소방차 fire_v2 후보(S2 설계 반영, 가정값 포함) 초기 선별 — 정지·대각(축별 기준)·요철·50 km/h 직선. chain_ft(현재 모델, 기준선) 뒤에.
cd "$(dirname "$0")/../../.."
until grep -q CHAIN_FT_DONE logs/ugv/stage6/chain_ft.out 2>/dev/null; do sleep 20; done
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle && bash ugv/tools/susp_static_test.sh ../ADAIR/logs/ugv/stage6/susp_static_ft2 fire_v2_base:adair_flat_susp:60:adair_firetruck fire_v2:adair_flat_susp:60:adair_firetruck fire_v2_base:adair_flat_diag2ft2:60:adair_firetruck fire_v2:adair_flat_diag2ft2:60:adair_firetruck fire_v2_base:adair_flat_diag5ft2:60:adair_firetruck fire_v2:adair_flat_diag5ft2:60:adair_firetruck" > logs/ugv/stage6/static_ft2.out 2>&1
bash logs/ugv/stage6/run_drive.sh fire_v2_base:adair_flat_susp:bump:a:adair_firetruck fire_v2:adair_flat_susp:bump:a:adair_firetruck fire_v2:adair_flat:straight50:a:adair_firetruck fire_v2_base:adair_flat:straight50:a:adair_firetruck fire_v2:adair_flat:straight50:b:adair_firetruck > logs/ugv/stage6/drive_ft2.out 2>&1
echo "CHAIN_FT2_DONE $(date)"
