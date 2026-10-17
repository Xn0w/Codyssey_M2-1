# -*- coding: utf-8 -*-
"""미션 정체 감지(드라이버 STALL_DETECT → 차량 MISSION_STALL 고장·정지)와 속도 계획 곡률 창.

2026-10-17 통합 B 교차로 494862: 속도 계획이 곡률을 앞뒤 15 m 로 봐 반경 8.2 m 원호를 완만하게 보고 3.41~3.96 m/s 를 실었다
(곡선 속도 2.86 m/s). PX4 가 항목을 도착 반경 밖으로 놓치고 맴돌다 이탈 → OFF_ROAD.
정체 감지는 연구 트리(ADAIR_wt_hook) 시험 test_fault_stop.py 의 정체 부분을 옮긴 것 (건너뛰기는 이식하지 않음).
"""
import asyncio
import math
from types import SimpleNamespace

import ugv.drivers.px4 as P
import ugv.vehicle as VM
from ugv import config
from ugv.drivers.base import Progress
from ugv.drivers.px4 import ACCEPT_M, stall_away
from ugv.geo import FRAME
from ugv.roads import plan_speeds
from ugv.tests.test_multi_vehicle import body, make_fleet


def test_stall_away_conditions():
    assert not stall_away(2.0, 1.0)                        # 도착 반경 안 — PX4 가 곧 넘긴다
    assert not stall_away(ACCEPT_M + 1.0, ACCEPT_M)        # 아직 최소 거리 + 1.5 m 안 (다가오는 중·옆을 지나는 중)
    assert stall_away(ACCEPT_M + 2.5, ACCEPT_M)            # 놓치고 멀어짐
    assert not stall_away(10.0, 9.5)                       # 멀리서 다가오는 중이었다면 최소 거리 기준으로는 멀어짐 아님


def _drv():
    d = P.Px4Driver("udp://x", None)
    d._armed = True
    d._seen_running = True                            # 이 미션의 PX4 진행 보고를 받은 뒤
    sent = [(float(x), 0.0, 4.0, True) for x in range(0, 60, 2)]
    d._sent = (1, sent)
    d._prog = Progress(10, len(sent), False, 1)
    state = {"x": 18.0, "y": 0.0, "age": 0.0}

    class Tel:
        def __init__(s):
            s.x, s.y, s.heading_deg, s.speed_mps = state["x"], state["y"], 90.0, 4.0

        def age_s(s):
            return state["age"]
    d.telemetry = lambda: Tel()
    return d, state


def test_stall_timer_lifecycle():
    """정체 타이머: 멀어지면 시작, 항목 변경·새 미션·텔레메트리 지연·시동 꺼짐·미션 끝이면 지운다."""
    d, st = _drv()
    d._stall_step()                                   # 항목 10(x=20) 2 m 앞 — 최소 거리 2
    assert d.stall_since is None
    st["x"], st["y"] = 21.0, 6.0                      # 옆으로 지나쳐 멀어짐 (6.1 m > 3.5, > 2 + 1.5)
    d._stall_step()
    assert d.stall_since is not None and d.stall_events[-1]["item"] == 10
    d._prog = Progress(11, d._prog.total, False, 1)  # PX4 가 다음 항목으로 넘김 → 지움
    d._stall_step()
    assert d.stall_since is None
    d._prog = Progress(10, d._prog.total, False, 1)
    st["x"], st["y"] = 18.0, 0.0
    d._stall_step()
    st["x"], st["y"] = 21.0, 6.0
    d._stall_step()
    assert d.stall_since is not None
    st["age"] = 5.0                                    # 텔레메트리 지연 → 지움
    d._stall_step()
    assert d.stall_since is None
    st["age"] = 0.0
    d._armed = False                                   # 시동 꺼짐 → 지움
    d._stall_step()
    assert d.stall_since is None
    d._armed = True
    d._sent = (2, d._sent[1])                          # 새 미션 번호인데 진행 보고는 옛 미션 → 판단 보류·지움
    d._stall_step()
    assert d.stall_since is None
    d._sent = (1, d._sent[1])
    d._prog = Progress(len(d._sent[1]), len(d._sent[1]), True, 1)   # 미션 끝 → 판단하지 않음
    d._stall_step()
    assert d.stall_since is None


def test_stall_not_judged_during_upload_or_before_progress():
    """미션 업로드·시작 중(_cmd 잠김), 새 미션 진행 보고 전, 시작 항목(k0) 앞 항목에서는 정체로 보지 않는다 —
    주행 중 재계획에서 로컬 Progress(0) 의 선행 항목 0 (차 뒤)을 기준으로 정체가 켜지던 오작동 (2026-10-17 검증)."""
    d, st = _drv()
    st["x"], st["y"] = 21.0, 6.0                      # 항목 10 기준이면 멀어짐
    d._stall_dmin, d._stall_key = 2.0, (1, 10)
    d._seen_running = False                           # 진행 보고 전
    d._stall_step()
    assert d.stall_since is None
    d._seen_running = True
    d._stall_k0 = 11                                  # 시작 항목이 11 인데 진행 보고는 아직 10
    d._stall_step()
    assert d.stall_since is None
    d._stall_k0 = 0

    async def locked():
        async with d._cmd:                            # 업로드·시작 중
            d._stall_step()
            assert d.stall_since is None
    asyncio.run(locked())
    d._stall_key = None
    d._stall_step()                                   # 항목 10 첫 판정 (최소 거리 = 지금 거리)
    st["x"], st["y"] = 23.0, 9.0
    d._stall_step()
    assert d.stall_since is not None                  # 가드가 풀리면 정상 판정


def test_stall_watch_follows_setting(monkeypatch):
    """STALL_DETECT 기본 켬. 끄면(UGV_PX4_STALL_DETECT=0) 감시 작업을 만들지 않는다."""
    import importlib
    monkeypatch.delenv("UGV_PX4_STALL_DETECT", raising=False)
    assert importlib.reload(P).STALL_DETECT is True
    monkeypatch.setenv("UGV_PX4_STALL_DETECT", "0")
    assert importlib.reload(P).STALL_DETECT is False
    monkeypatch.delenv("UGV_PX4_STALL_DETECT")
    importlib.reload(P)


def test_vehicle_mission_stall_faults_and_stops(tmp_path):
    """드라이버 정체가 STALL_FAULT_S 이어지면 차량은 MISSION_STALL 고장(작업 FAILED)·정지. 짧은 정체는 고장이 아니다."""
    async def go():
        f, clock = make_fleet(tmp_path)
        A = f.vehicles["A-ugv1"]
        tgt = FRAME.to_ll(A.access.x - 900, A.access.y - 700)
        await A.execute(body("S1", *tgt))
        for _ in range(20):
            clock.advance(0.5)
            A.driver.step(0.5)
            await A.tick()
        assert A.state == "DRIVING"
        A.driver.stall_since = VM.time.monotonic()            # 방금 시작한 정체 — 아직 고장 아님
        await A.tick()
        assert A.state == "DRIVING" and A.fault is None
        A.driver.stall_since = VM.time.monotonic() - VM.STALL_FAULT_S - 0.1
        await A.tick()
        assert A.state == "FAULT" and A.fault.startswith("MISSION_STALL")
        assert A.driver.stall_since is None
        assert f.store.tasks["S1"]["status"] == "FAILED"
    asyncio.run(go())


def _arc_route(R=8.2, turn_deg=90.0, lead=60.0, tail=60.0, step=0.5):
    """직선 lead m → 반경 R 원호 → 직선 tail m (교차로 급회전 모양)."""
    pts = [(-lead + k * step, 0.0) for k in range(int(lead / step))]
    n = int(math.radians(turn_deg) * R / step)
    for k in range(n + 1):
        a = math.radians(turn_deg) * k / n
        pts.append((R * math.sin(a), -R * (1 - math.cos(a))))           # 오른쪽 회전
    ex, ey = pts[-1]
    h = -math.radians(turn_deg)
    pts += [(ex + k * step * math.cos(h), ey + k * step * math.sin(h)) for k in range(1, int(tail / step))]
    return SimpleNamespace(pts=pts, vlim=[20.0] * len(pts))          # plan_speeds 는 pts·vlim 만 쓴다


def test_curve_speed_follows_turn_radius():
    """속도 계획 곡선 속도가 실제 회전반경을 따른다: R 8.2 m 원호에 실린 최소 항목 속도 ≤ √(횡가속 × R) (+ 0.1 m/s 반올림 여유).
    곡률 창 15 m 였을 때는 R 을 11~14 m 로 봐 약 3.4~3.7 m/s (횡가속 1.0) — 2026-10-17 통합 B."""
    lat = 1.0
    sp = plan_speeds(_arc_route(), 0.0, lat_accel=lat)
    v_turn = math.sqrt(lat * 8.2)
    arc_items = [v for x, y, v in sp.items if x > -2.0 and y > -8.2 - 2.0 and x < 8.2 + 2.0 and abs(y) > 0.3]
    assert arc_items and min(arc_items) <= v_turn + 0.1, (min(arc_items), v_turn)
    assert config.CURVE_WINDOW_M <= config.ITEM_CURVE_WINDOW_M


def test_item_speed_covers_acceptance_lead():
    """PX4 는 앞 지점 도착 반경(3 m) 안에서 다음 구간 속도를 먼저 쓴다 → 지점 속도 ≤ (앞 지점 − ITEM_SPEED_LEAD_M ~ 이 지점) 계획 최소.
    원호 지점 간격 2.2 m 에서 정점 뒤 구간 속도가 정점 앞에서 먼저 적용되던 결함 (2026-10-17 교차로 494862, 정점 실제 3.09 m/s)."""
    import bisect
    lat = 1.0
    sp = plan_speeds(_arc_route(), 0.0, lat_accel=lat)
    pos = {(round(x, 6), round(y, 6)): k for k, (x, y) in enumerate(sp.pts)}
    idx = [pos[(round(x, 6), round(y, 6))] for x, y, _ in sp.items_on_path]      # 곡선 보정 전 (계획 선형 위) 좌표
    for n in range(1, len(idx) - 1):
        a = bisect.bisect_left(sp.cum, sp.cum[idx[n - 1]] - ACCEPT_M)          # PX4 도착 반경 (드라이버 값) 기준
        lo = min(v for k, v in enumerate(sp.v[a:idx[n] + 1], a) if sp.cum[k] >= config.ITEM_FIRST_MIN_M)
        assert sp.items[n][2] <= max(lo, 1.0) + 0.01, (n, sp.items[n][2], lo)
    # 원호(정점 ±3 m) 안에 실린 속도는 곡선 속도 이하
    apex = min(range(len(sp.v) - 1), key=lambda k: sp.v[k] if sp.cum[k] > 10 else 1e9)
    near = [sp.items[n][2] for n in range(len(idx)) if abs(sp.cum[idx[n]] - sp.cum[apex]) <= 3.0]
    assert near and max(near) <= math.sqrt(lat * 8.2) + 0.1, near
