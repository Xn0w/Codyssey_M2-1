# -*- coding: utf-8 -*-
"""추적할 시도가 없어도 추적 주기마다 UGV 서버에 연락한다 (UGV 총괄 통신 단절 규칙이 '할 일 없음'으로 잘못 걸리지 않게)."""
from orchestrator.engine import Orchestrator
from orchestrator.env_adapter import FixtureEnv
from orchestrator.ledger import Ledger


class _Ugv:
    def __init__(self, fail=False):
        self.calls, self.fail = 0, fail

    def states(self):
        self.calls += 1
        if self.fail:
            raise RuntimeError("down")
        return []


def test_ugv_contact_polls_even_without_attempts(tmp_path):
    u = _Ugv()
    orch = Orchestrator(Ledger(str(tmp_path / "l.db")), FixtureEnv(), ugv=u)
    assert orch.ledger.list_attempts() == []
    assert orch.ugv_contact() is True and u.calls == 1


def test_ugv_contact_failure_is_ignored(tmp_path):
    u = _Ugv(fail=True)
    orch = Orchestrator(Ledger(str(tmp_path / "l.db")), FixtureEnv(), ugv=u)
    assert orch.ugv_contact() is False and u.calls == 1
    assert Orchestrator(Ledger(str(tmp_path / "m.db")), FixtureEnv()).ugv_contact() is False
