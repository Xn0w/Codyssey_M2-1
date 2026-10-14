"""ETA 상한 오프라인 분석 (Fable 미해결 5.1) — pytest 플러그인 (-p eta_dump_plugin). 기존 시험이 부르는 approach._plan_once 의
`ok` 후보 전체(지점·목표 거리·도착 시간)와 실제 선택을 JSONL 로 남긴다. 코드 동작은 바꾸지 않는다 (기록 한 줄만 끼움, 저장소 파일 수정 없음).
출력: 환경변수 ETA_DUMP_OUT (기본 eta_dump.jsonl)."""
import inspect
import json
import os
import textwrap

OUT = os.getenv("ETA_DUMP_OUT", "eta_dump.jsonl")
_seq = [0]


def _rec(kind, L):
    try:
        _seq[0] += 1
        row = {"seq": _seq[0], "kind": kind, "test": os.getenv("PYTEST_CURRENT_TEST", "").rsplit(" ", 1)[0]}
        if kind == "cands":
            st = L["start"]
            row.update(target_xy=[round(L["tx"], 2), round(L["ty"], 2)], start_xy=[round(st.pos.x, 2), round(st.pos.y, 2)],
                       fixed_dest=L["fixed_dest"] is not None, relax=sorted(map(str, L["relax"])) if L["relax"] else [],
                       avoid=len(L["avoid"] or ()), arrive_toward=L["arrive_toward"],
                       ok=[[o[0].road_id, round(o[0].s, 2), round(o[1], 2), round(o[3], 2)] for o in L["ok"]])
        else:
            d = L["dest"]
            row.update(chosen=[d.road_id, round(d.s, 2), round(L["d"], 2), round(L["t"], 2)],
                       sel={k: (None if v is None else round(v, 2)) for k, v in L["sel"].items()})
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001 — 기록 실패가 시험을 바꾸지 않게
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps({"seq": _seq[0], "kind": "dump_error", "error": repr(e)[:200]}) + "\n")


def _instrument():
    import ugv.approach as A
    src = textwrap.dedent(inspect.getsource(A._plan_once))
    a = '    counts = {"candidates_no_directed_route": no_route, "candidates_no_return_path": no_return}\n'
    b = '    route = g.build_route(tree, dest, arr, relax)\n'
    assert src.count(a) == 1 and src.count(b) == 1, "approach._plan_once 모양이 바뀜 — 덤프 위치 재확인"
    src = src.replace(a, a + '    _ETA_DUMP("cands", locals())\n').replace(b, '    _ETA_DUMP("chosen", locals())\n' + b)
    ns = A.__dict__
    ns["_ETA_DUMP"] = _rec
    exec(compile(src, A.__file__, "exec"), ns)          # 같은 모듈 이름공간에 다시 정의 (approach.plan 이 이름으로 부름)


def pytest_configure(config):
    _instrument()
