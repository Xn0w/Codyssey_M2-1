# -*- coding: utf-8 -*-
"""화재 자료 신선도 — 받지 못함·오래됨·미설정을 '화재 없음' 으로 보지 않는다 (2026-10-11 검토 재현: 실패한 시도가 수신 시각을
갱신해 단절 중에도 age 0 s, 첫 수신 실패면 빈 화재 영역으로 계획)."""

import asyncio
import time

import pytest

from ugv import config
from ugv.fire import EnvHttpFireSource, StaticFireSource, build_source
from ugv.geo import FRAME
from ugv.vehicle import HttpError
from ugv.tests.test_multi_vehicle import FLEET_CFG, body, make_fleet


class _Resp:
    def __init__(self, d):
        self.d = d

    def raise_for_status(self):
        pass

    def json(self):
        return self.d


class _Client:
    def __init__(self):
        self.fail, self.snap = True, None

    def get(self, url):
        if self.fail:
            raise ConnectionError("TEST_ENV_DOWN")
        return _Resp(self.snap)


def _snap(version, run="R1", n=1):
    la, lo = FRAME.to_ll(0.0, 0.0)
    return {"state_version": version, "run_id": run, "simulation_time_s": 1.0,
            "fire_cells": [{"cell_id": f"c{i}", "lat": la, "lon": lo + i * 0.001, "fire_state": "BURNING"} for i in range(n)]}


def test_env_source_states_and_success_age():
    c = _Client()
    src = EnvHttpFireSource("http://x", client=c, background=False)
    src._fetch()
    assert src.data_status() == "NEVER_RECEIVED" and src.status()["age_s"] is None and len(src.area()) == 0
    assert src.status()["usable"] is False
    c.fail, c.snap = False, _snap(1)
    src._fetch()
    assert src.data_status() == "FRESH" and len(src.area()) == 1
    a1 = src.area()
    src._fetch()                                                # 같은 버전 재수신 — 다시 만들지 않는다
    assert src.area() is a1 and src.data_status() == "FRESH"
    c.snap = _snap(1, run="R2", n=2)                            # run_id 교체 — 새로 만든다
    src._fetch()
    assert len(src.area()) == 2 and src.run_id == "R2"
    src._ok_mono = time.monotonic() - 3600                      # 한 시간 전 성공, 지금 실패
    c.fail = True
    src._fetch()
    st = src.status()
    assert st["age_s"] >= 3599 and st["data_status"] == "STALE" and st["error"] and st["attempt_age_s"] < 1.0
    assert len(src.area()) == 2                                 # 마지막 값은 보관 (진행 중 차의 안전 판단용)
    c.fail = False
    src._fetch()
    assert src.data_status() == "FRESH"


def test_build_source_without_env_needs_explicit_permission(monkeypatch):
    monkeypatch.setattr(config, "ENV_URL", "")
    monkeypatch.setattr(config, "ALLOW_NO_FIRE_DATA", False)
    assert build_source().data_status() == "NOT_CONFIGURED"
    monkeypatch.setattr(config, "ALLOW_NO_FIRE_DATA", True)
    assert build_source().data_status() == "STATIC"


@pytest.mark.parametrize("state", ["NEVER_RECEIVED", "STALE", "NOT_CONFIGURED"])
def test_new_fire_task_rejected_without_usable_fire_data(tmp_path, state):
    async def go():
        f, clock = make_fleet(tmp_path, [FLEET_CFG[0]])
        A = f.vehicles["A-ugv1"]
        if state == "NOT_CONFIGURED":
            A.fire_source = StaticFireSource(source="NONE", explicit=False)
        else:
            c = _Client()
            src = EnvHttpFireSource("http://x", client=c, background=False)
            if state == "STALE":
                c.fail, c.snap = False, _snap(1)
                src._fetch()
                src._ok_mono = time.monotonic() - 3600
                c.fail = True
            src._fetch()
            A.fire_source = src
        tgt = FRAME.to_ll(A.access.x - 900, A.access.y - 700)
        ev = await A.evaluate(body("F1", *tgt))
        assert ev["verdict"] == "REJECT" and ev["reason"] == "FIRE_DATA_UNAVAILABLE" and state in ev["detail"]
        with pytest.raises(HttpError) as e:
            await A.execute(body("F1", *tgt))
        assert e.value.args[0]["reason"] == "FIRE_DATA_UNAVAILABLE"
        assert A.state == "IDLE" and A.current_task() is None
    asyncio.run(go())
