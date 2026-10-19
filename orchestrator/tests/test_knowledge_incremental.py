# -*- coding: utf-8 -*-
"""Knowledge.fire_states 증분 계산이 전부 다시 접은 결과와 같은지 (2026-10-19, 관제판 지연 수정)."""

import random

import pytest

from orchestrator.knowledge import Knowledge


@pytest.fixture(autouse=True)
def active_run(world):
    world["orch"].view()                                 # 환경 snapshot 으로 run 활성화

STATUSES = ("REPORTED", "CONFIRMED", "CONFIRMED_BURNED", "OBSERVED_CLEAR", "NOT_DETECTED_PARTIAL")


def _full(kb, now):
    return Knowledge._fold_all(kb.ledger.knowledge("FIRE"), now)


def _add(kb, i, cell, t, status):
    kb.ledger.add_knowledge("FIRE", f"K{i}", cell, t, "TEST",
                            {"cell_id": cell, "status": status, "observation_id": f"O{i}", "coverage_fraction": 0.4})


def test_incremental_matches_full_fold_random(world):
    kb = world["orch"].kb
    rng = random.Random(20261019)
    now, i = 0.0, 0
    for step in range(600):
        for _ in range(rng.randint(0, 4)):
            i += 1
            r = rng.random()
            if r < 0.1:
                t = None                                 # 시각 불명
            elif r < 0.2:
                t = now + rng.choice([60.0, 120.0])      # 미래 시각 사실
            elif r < 0.3:
                t = max(0.0, now - rng.choice([60.0, 600.0]))   # 늦게 들어온 과거 사실 (순서 앞에 낌)
            else:
                t = now
            _add(kb, i, f"c{rng.randint(0, 15)}", t, rng.choice(STATUSES))
        if rng.random() < 0.7:
            now += 60.0
        r = rng.random()
        if r < 0.15:
            q = max(0.0, now - rng.choice([60.0, 300.0, 900.0]))     # 창 안 과거 시각 (스레드마다 읽은 시각 차이)
        elif r < 0.18:
            q = max(0.0, now - 5000.0)                               # 창 밖 과거 시각
        else:
            q = now
        assert kb.fire_states(q) == _full(kb, q), step


def test_incremental_reads_only_new_rows(world, monkeypatch):
    kb = world["orch"].kb
    for i in range(50):
        _add(kb, i, f"c{i % 7}", 60.0 * i, "CONFIRMED")
    kb.fire_states(6000.0)
    calls = []
    monkeypatch.setattr(kb.ledger, "knowledge", lambda *a, **k: calls.append(a) or [])
    _add(kb, 99, "c1", 6000.0, "OBSERVED_CLEAR")
    out = kb.fire_states(6000.0)
    assert calls == []                                   # 전부 다시 읽지 않는다
    assert out["c1"]["status"] == "OBSERVED_CLEAR"


def test_returned_dict_is_a_copy(world):
    kb = world["orch"].kb
    _add(kb, 1, "c1", 0.0, "CONFIRMED")
    a = kb.fire_states(60.0)
    a["c1"]["status"] = "MUTATED"
    a.pop("c1")
    assert kb.fire_states(60.0)["c1"]["status"] == "CONFIRMED"


def test_report_rows_and_count_match_full_read(world):
    orch = world["orch"]
    kb, lg = orch.kb, orch.ledger

    def full_reports():
        return [{"report_id": k["key"], "cell_id": k["subject"], "sim_time_s": k["sim_time_s"], "source": k["source"]}
                for k in lg.knowledge("FIRE") if (k["body"] or {}).get("status") == "REPORTED"]
    rng = random.Random(7)
    for i in range(200):
        t = None if rng.random() < 0.05 else 60.0 * rng.randint(0, 30)    # 늦게 들어온 과거·시각 불명 신고 포함
        _add(kb, 1000 + i, f"c{i % 5}", t, rng.choice(STATUSES))
        if rng.random() < 0.3:
            assert orch._report_rows() == full_reports(), i
    assert orch._report_rows() == full_reports()
    assert lg.knowledge_count("FIRE") == len(lg.knowledge("FIRE"))


def test_past_query_inside_window_does_not_reread_all(world, monkeypatch):
    kb = world["orch"].kb
    for i in range(40):
        _add(kb, i, f"c{i % 6}", 60.0 * i, STATUSES[i % len(STATUSES)])
    kb.fire_states(2400.0)
    calls = []
    real = kb.ledger.knowledge
    monkeypatch.setattr(kb.ledger, "knowledge", lambda *a, **k: calls.append(a) or real(*a, **k))
    got = kb.fire_states(2100.0)
    assert calls == []                                   # 창 안 과거 조회는 전부 다시 읽지 않는다
    monkeypatch.setattr(kb.ledger, "knowledge", real)
    assert got == _full(kb, 2100.0)
    assert kb.fire_states(2400.0) == _full(kb, 2400.0)   # 캐시는 그대로


def test_past_query_sees_rows_parked_by_earlier_past_query(world):
    # 리뷰 2026-10-19: 과거 조회가 (now_s, 캐시 시각] 사이 새 행을 pending 에 넣은 뒤,
    # 그 행 시각 이후의 과거 조회가 그 행을 빠뜨리던 것
    kb = world["orch"].kb
    _add(kb, 1, "c1", 100.0, "CONFIRMED")
    kb.fire_states(1000.0)                               # 캐시 시각 1000
    _add(kb, 2, "c1", 500.0, "OBSERVED_CLEAR")
    assert kb.fire_states(200.0) == _full(kb, 200.0)     # 행 2 는 pending 으로
    assert kb.fire_states(600.0) == _full(kb, 600.0)     # 행 2 가 들어가야 한다
    assert kb.fire_states(600.0)["c1"]["status"] == "OBSERVED_CLEAR"
    assert kb.fire_states(1000.0) == _full(kb, 1000.0)
