# r2_check 판정기 정정 기록 (2026-10-14, Codex 0940 1절)
- 원본 r2_check_v1_orig.py (sha1 f05e178b, SEAMC_R2_freeze.sha1 의 동결본) 은 sc_R2 결과 JSON 을 쓰다 numpy bool 직렬화 오류로 중단 (r2check 첫 출력은 Traceback — 불완전 출력).
- 정정본 r2_check.py (sha1 7fc8f036) = 체크 값을 `None 아니면 bool()` 로 정규화하는 한 줄. **판정 동작 영향 있음** (오퍼스의 '판정 불변' 설명 정정): 상태 규칙 `any(v is False …)` 는 numpy.bool_(False) 를 False 로 보지 못해 원본은 numpy False 를 PASS 로 둘 수 있었음. 분류 확인 r2_check_status_classify.out: np_False v1 PASS → v1.1 FAIL, py_False FAIL/FAIL, None UNCONFIRMED/UNCONFIRMED, np_True PASS/PASS, np_False+None v1 UNCONFIRMED → v1.1 FAIL.
- sc_R2 는 11 체크 모두 True 라 결과 불변 (PASS). 물리 재실행 불필요. 동결표 해시는 원본 기준 그대로 두고 (실행 전부터 같은 분석기였다고 바꾸지 않음), 후속 기준은 정정본 해시로 고정.
- 같은 위험 점검: 이번 캠페인의 다른 판정기 (final_judge_v7_1·e4_judge_v3/ops·envA_check·envB_extra·seam_check(_c1)) 는 체크 dict 를 json.dump 하므로 numpy bool 이 섞였다면 직렬화가 실패했을 것 — 모든 실행에서 JSON 이 써졌으므로 numpy bool 없음. 이후 사본 (envB_c1/envB_extra.py, detail_check.py) 은 같은 정규화를 넣음.
