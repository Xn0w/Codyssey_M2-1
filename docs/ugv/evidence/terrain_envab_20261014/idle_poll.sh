#!/usr/bin/env bash
# 단계 A 시험 명령 (미션 전송 없음): 서버 /ugv 를 2 s 마다 90 s 기록 (상태·위치·sim 시각·갱신 시각) — 정지 상태 텔레메트리 신선도
OUT=$1; : > $OUT
for i in $(seq 45); do echo "{\"wall\":$(date +%s.%N | cut -c1-14),\"ugv\":$(curl -s -H 'X-ADAIR-Monitor: 1' http://127.0.0.1:8100/ugv || echo null)}" >> $OUT; sleep 2; done
