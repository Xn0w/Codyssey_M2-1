# 수정 후보 c1 — 정적 게이트·정지 재현 사전 기준 (2026-10-14 09:3x, 실행 전, Codex 0920)

## 후보 c1 (단일 변경)
T04_16·T05_16 두 타일만 별도 루트 `terrain_ab/seamC/tiles_c1/` 에 복사, **collision heightmap size X/Y 1000 → 1000.9765625 (= 1000·1025/1024)** 한 항목만 변경 (+ 설명 주석; 줄바꿈 CRLF→LF). visual size 1000·model pose·PNG (해시 동일)·수직 size·마찰·model.config 불변. 원본 tiles_v2·운영 지도·차량·엔진/step 불변. 160 타일 일괄 적용 없음.
근거: SRC_chain.md (gz-physics 7.8.0 `scale = size/vertSize`) → 후보 scale 0.9765625 = 1000/1024, ODE 폭 1000, 반폭 500.

## 정적 게이트 (c1_static_gate.py → c1_static_gate.json) — **PASS**
N=1025·uint16·sampling 태그 없음·PNG 동일·pose·visual size·수직 size 불변, 충돌 꼭짓점 국소 좌표 = −500 + i·1000/1024 (X·Y 양축, 네 모서리·사분점·중심 포함 최대 차 0.0), 공유 가장자리 x 4380.0 = 4380.0 (틈 0, 원본 0.97561), 공유 가장자리 높이 차 최대 0.0027 m (p99 0.0024). 실제 엔진 반영은 기동 때 AABB 로 확인.

## 정지 재현 (seam_static_c1.sh, chain_seamC.sh)
seam_static.sh 와 차이: 모델 검색 `GZ_SIM_RESOURCE_PATH = tiles_c1 : tiles_v2` (후보 두 타일만 후보 루트에서 해석), **기동 뒤 gz 로그 AABB 반폭 500 이 정확히 2 줄·499.512 가 158 줄이 아니면 invalid_evidence (시험 안 함)** — 각 기동의 실제 해석 증거 (aabb_<TAG>.json). 차량·엔진·step·yaw −2.5652·y 5928.044·스폰 규칙 (지면 + 0.45)·기록기 (gz_detail_seam.py 동일 사본)·중단 신호 그대로.
회차: cR0a (x 4400, 기대 T05_16) → cR0b (x 4360, 기대 T04_16) → cR1a (x 4380.6959, FL 이 원래 띠 위; 기대 T04_16|T05_16). **세 회차 모두 같은 건전성 기준** (seam_check_c1.py, kind R0): 기록기 rc 0·표식 없음, 서스펜션 발행, 네 바퀴 VALID ≥ 95 %, 접촉 상대 기대 타일, **Σfz 원본 R0a 15,915.2 N ± 3 %** (이중면 과잉 하중), **바퀴별 접선/법선 힘 중앙값 비 ≤ 0.10** (불연속 법선), |롤|·|피치| ≤ 2°, 서스펜션 |q| < 0.098, 바퀴 link z − 분석 지면 ∈ [0.29, 0.41]. 판정기 확인: 원본 sr_R0a PASS, 원본 sr_R1a FAIL (VALID·타일·ft/fn·자세·높이 거짓).
접촉 깊이는 기록 한계 (항상 0) — 수치 만들지 않음. 후보 R1a 의 NO_MSG 는 계측 불명/지지 이상으로 HOLD.
순서: cR0a → PASS 면 cR0b → PASS 면 cR1a → **멈춤·보고**. R2 저속 통과는 결과 뒤 별도 동결.
