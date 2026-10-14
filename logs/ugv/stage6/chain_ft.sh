#!/usr/bin/env bash
# 2026-10-12 차량 개조 P5: 소방차 강체 대각 하중 확인(S1·S2) → 후보 susp_a(축별 K·C) 정적·요철·50 km/h 직선. 교차로 체인(chain59) 뒤에 (부하 분리).
cd "$(dirname "$0")/../../.."
until grep -q CHAIN59_DONE logs/ugv/stage4/chain59.out 2>/dev/null; do sleep 20; done
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- bash -lc "cd /mnt/c/Users/수다쟁이고양이들/Documents/GitHub/ADAIR_wt_vehicle && bash ugv/tools/susp_static_test.sh ../ADAIR/logs/ugv/stage6/susp_static_ft base:adair_flat_susp:60:adair_firetruck susp_a:adair_flat_susp:60:adair_firetruck base:adair_flat_diag2ft:60:adair_firetruck susp_a:adair_flat_diag2ft:60:adair_firetruck base:adair_flat_diag5ft:60:adair_firetruck susp_a:adair_flat_diag5ft:60:adair_firetruck" > logs/ugv/stage6/static_ft.out 2>&1
bash logs/ugv/stage6/run_drive.sh base:adair_flat_susp:bump:a:adair_firetruck susp_a:adair_flat_susp:bump:a:adair_firetruck susp_a:adair_flat:straight50:a:adair_firetruck base:adair_flat:straight50:a:adair_firetruck base:adair_flat:straight50:b:adair_firetruck susp_a:adair_flat:straight50:b:adair_firetruck > logs/ugv/stage6/drive_ft.out 2>&1
echo "CHAIN_FT_DONE $(date)"
