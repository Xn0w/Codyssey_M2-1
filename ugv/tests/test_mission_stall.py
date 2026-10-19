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


def _arc_route(R=8.2, turn_deg=90.0, lead=60.0, tail=60.0, step=0.5, tail_step=None):
    """직선 lead m → 반경 R 원호 → 직선 tail m (교차로 급회전 모양). tail_step: 뒤 직선 점 간격 (기본 step)."""
    pts = [(-lead + k * step, 0.0) for k in range(int(lead / step))]
    n = int(math.radians(turn_deg) * R / step)
    for k in range(n + 1):
        a = math.radians(turn_deg) * k / n
        pts.append((R * math.sin(a), -R * (1 - math.cos(a))))           # 오른쪽 회전
    ex, ey = pts[-1]
    h = -math.radians(turn_deg)
    ts = tail_step or step
    pts += [(ex + k * ts * math.cos(h), ey + k * ts * math.sin(h)) for k in range(1, int(tail / ts))]
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


def _arc_span(sp, R=8.2, turn_deg=90.0):
    """_arc_route 원호 구간 [접점, 끝점] 의 진행 거리 (출발 lead m 뒤부터 원호 길이만큼)."""
    s0 = sp.cum[min(range(len(sp.pts)), key=lambda k: math.dist(sp.pts[k], (0.0, 0.0)))]
    return s0, s0 + math.radians(turn_deg) * R


def test_plan_speed_whole_arc_including_ends_le_curve_speed():
    """원호 시작·끝(접점 근처)까지 계획 속도 ≤ √(횡가속 × R) — 앞뒤 5 m 창 세 점 원은 원호 끝 약 5 m 안에서 직선을 섞어
    원호 시작 1.1 m 안 3.36 m/s, 끝 4 m 에 3.10~3.87 m/s 를 계획했다 (2026-10-19 교차로 494862 20회, R 8.41 m 곡선 속도 2.90).
    원호에 걸치는 PX4 구간 속도(앞 지점 도착 반경부터 적용)도 곡선 속도 이하."""
    lat = 1.0
    for R, step in ((8.41, 1.1), (10.28, 1.26), (8.2, 0.5)):
        sp = plan_speeds(_arc_route(R=R, step=step), 0.0, lat_accel=lat)
        vc = math.sqrt(lat * R)
        s0, s1 = _arc_span(sp, R)
        on_arc = [sp.v[k] for k in range(len(sp.v)) if s0 - 0.01 <= sp.cum[k] <= s1 + 0.01]
        assert on_arc and max(on_arc) <= vc + 0.01, (R, max(on_arc), vc)
        # 원호 안은 곡선 속도보다 쓸데없이 낮추지 않는다
        assert min(on_arc) >= vc - 0.05, (R, min(on_arc), vc)
        pos = {(round(x, 6), round(y, 6)): k for k, (x, y) in enumerate(sp.pts)}
        idx = [pos[(round(x, 6), round(y, 6))] for x, y, _ in sp.items_on_path]
        for n in range(1, len(idx)):
            lo_s = sp.cum[idx[n - 1]] - ACCEPT_M                    # 이 구간 속도가 적용되기 시작하는 곳
            if lo_s <= s1 and sp.cum[idx[n]] >= s0:
                assert sp.items[n][2] <= vc + 0.01, (R, n, sp.items[n][2], vc)


def test_side_window_curvature_not_used_on_gentle_bends_and_straights():
    """반쪽 창 곡률은 급한 곡선(CURVE_SIDE_R_M 미만)에만 — 완만한 굽이(R 50 m 다듬은 원호)와 원호에서 창 밖 직선은 예전(앞뒤 창)과 같다."""
    from ugv.roads import _curvature, _plan_curvature
    sp = plan_speeds(_arc_route(R=50.0, turn_deg=12.0, step=1.0), 0.0, lat_accel=1.0)
    for k in range(len(sp.pts)):
        assert _plan_curvature(sp.pts, sp.cum, k, config.CURVE_WINDOW_M) == _curvature(sp.pts, sp.cum, k, config.CURVE_WINDOW_M)
    sp = plan_speeds(_arc_route(R=8.41, step=1.1), 0.0, lat_accel=1.0)
    s0, s1 = _arc_span(sp, 8.41)
    for k in range(len(sp.pts)):
        if sp.cum[k] < s0 - config.CURVE_WINDOW_M or sp.cum[k] > s1 + config.CURVE_WINDOW_M:
            assert _plan_curvature(sp.pts, sp.cum, k, config.CURVE_WINDOW_M) == _curvature(sp.pts, sp.cum, k, config.CURVE_WINDOW_M)


def test_final_item_speed_covers_acceptance_lead():
    """마지막(도착) 구간 속도도 앞 지점 도착 반경(ITEM_SPEED_LEAD_M)부터 본다 — 예전에는 앞 지점 뒤부터만 봐서 2026-10-19 494862
    원호 3 끝 지점 3 m 앞에서 도착 구간 3.82 m/s 가 먼저 적용돼 원호 끝 실제 3.83 m/s (곡선 속도 3.21)."""
    pts = [(float(x), 0.0) for x in range(41)] + [(40.0 + 5.0 * k, 0.0) for k in range(1, 8)]     # 0~40 m 1 m 간격, 이후 5 m → 75 m 도착
    vlim = [3.0 if 37.5 <= x <= 39.5 else 20.0 for x, _ in pts]                               # 앞 지점(40 m) 직전 느린 구간
    sp = plan_speeds(SimpleNamespace(pts=pts, vlim=vlim), 0.0, lat_accel=1.0)
    (_, _, v_prev), (x_last, _, v_last) = sp.items_on_path[-2], sp.items_on_path[-1]
    assert x_last == 75.0 and sp.items_on_path[-2][0] == 40.0, sp.items_on_path
    assert v_last <= 3.0 + 0.01, v_last
