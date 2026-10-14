# B 단계 별도 진단 — 앞차축 y ±0.10 m 정지 대조 2 회 사전 기준 (2026-10-14, 실행 전, Codex 1045)
원 bR1y FAIL 유지 (ft/fn 만 거짓). 이 진단은 원 B 체인 재개가 아님. bR2y·bR1c·160 타일·A↔B HOLD.
## 고정 / 변경
고정 = 같은 4 타일 후보·차량·엔진/step·x 15400.8·yaw π/2·NO_PX4·무구동·센서·해석 증거 (AABB 4/156·prov 4)·중단 신호. **변경 = 중심 y 만**: bD_N −4632.25 (앞바퀴 y −4630.90, 경계 북쪽 0.10), bD_S −4632.45 (앞바퀴 y −4631.10, 남쪽 0.10). z = 중심 분석 지면 + 0.45 (101.992 / 101.993). 두 위치 모두 앞바퀴 접지 범위가 **보정 전 띠 안** (b4d_spawn_calc.json) — 보정 전 정상 대조로 표현하지 않음.
## 계측 (gz_detail_seam_v3 = v1 + 점별 원본 JSONL 0.1 s): 점별 collision1/2·position·normal·depth·body_1/body_2 force. 오프라인 의미 = OFFLINE_contact_semantics.md (DART force = 엔진 body1 에 작용·월드, normal = body2→body1, gz-sim 은 양쪽 메시지에 같은 값 → 바퀴 쪽 힘은 정지 지지 +z 로 추론).
## 판정
- seam_check_c1b.py (= seam_check_c1 + 주석 조건 정정 'kangwon_tile_T', 판정 불변): 기존 건전성 기준 그대로 (ft/fn ≤ 0.10 포함), 기대 타일 T16_05|T16_06.
- raw_check.py (판정 없음, 기록): 바퀴별 점 수·접촉 상대·엔진 body1 추론·점별 법선 기울기·법선 x 성분·점별 ft/fn·depth.
## 순서 (chain_seamB4d.sh)
bD_N → (전부 PASS 또는 ft/fn 만 거짓이고 표식·중단·NO_MSG 없음이면) bD_S → 멈춤·보고. 다른 이상 (NO_MSG·계측 실패·자세/행정 이상·표식) 이면 그 회차에서 멈춤. 오프셋 연속 탐색·파라미터 변경 없음.
## 해석 규칙 (사전)
두 오프셋 모두 PASS → '정확한 경계 배치에 국한된 의존성' 근거 (원 FAIL 은 유지, 정확히 경계에 서지 않는다는 가정으로 통과시키지 않음). 한쪽/양쪽 같은 힘 이상 또는 점별 normal/F 가 엔진 정의와 맞지 않음 → 경계 처리/원통 충돌/좌표 해석 추가 분리 + 기존 Fable 검토 재개 요청.
