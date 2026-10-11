# -*- coding: utf-8 -*-
"""PX4 미션 속도 의미 변환 — MAVSDK speed_m_s 는 '그 지점을 지난 뒤' 속도 (2026-10-09 실측)."""
import math

from ugv.drivers.px4 import ACCEPT_M, LEAD_BASE_M, LEAD_TIME_S, mavsdk_plan


def test_speeds_shift_one_item_earlier_and_lead_point_carries_first_segment():
    items = [(100.0, 0.0, 16.0), (140.0, 0.0, 8.0), (180.0, 0.0, 12.0), (200.0, 0.0, 3.0)]
    out = mavsdk_plan(items, (0.0, 0.0), 10.0)
    lead = LEAD_BASE_M + 10.0 * LEAD_TIME_S
    assert len(out) == 5
    assert math.isclose(out[0][0], lead) and out[0][2] == 16.0 and out[0][3]       # 첫 구간 속도는 선행 지점에
    assert [o[2] for o in out[1:]] == [8.0, 12.0, 3.0, 3.0]                        # 지점 k 에 k+1 구간 속도
    assert [o[3] for o in out] == [True, True, True, True, False]                  # 마지막만 정지


def test_no_lead_point_when_first_item_is_close():
    items = [(LEAD_BASE_M + ACCEPT_M - 1.0, 0.0, 5.0), (60.0, 0.0, 9.0)]
    out = mavsdk_plan(items, (0.0, 0.0), 0.0)
    assert [(o[0], o[2]) for o in out] == [(items[0][0], 9.0), (60.0, 9.0)]


def test_single_stop_point():
    out = mavsdk_plan([(0.0, 75.0, 16.0)], (0.0, 0.0), 16.0)
    assert out[-1] == (0.0, 75.0, 16.0, False) and out[0][2] == 16.0 and out[0][1] < 75.0


def test_first_mission_item_is_not_glued_to_start():
    """첫 미션 지점이 출발점에 붙어 출발 램프 속도(1 m/s)를 싣지 않는다 (2026-10-10 Gazebo G5b 기어감)."""
    import math
    from ugv import config
    from ugv.roads import Route, plan_speeds
    pts = [(0.0, 0.0), (0.3, 0.0), (40.0, 8.0), (120.0, 8.0)]
    sp = plan_speeds(Route(pts, [16.7] * 4, [], None, None, 0.0), 0.0)
    assert math.hypot(*sp.items[0][:2]) >= config.ITEM_FIRST_MIN_M - 1e-6
    assert sp.items[0][2] > 1.5


def test_park_due_also_parks_a_vehicle_that_keeps_driving_after_mission_end():
    """미션 끝 뒤 계속 달리면 RUNAWAY_PARK_S 뒤 시동을 끈다 (2026-10-11 Gazebo: 정지 경로 끝 2.9 m/s 로 FAULT 직진)."""
    from ugv.drivers.px4 import PARK_AFTER_S, RUNAWAY_PARK_S, park_due
    due, still, fin = park_due(2.9, 100.0, None, None)
    assert not due and still is None and fin == 100.0
    due, still, fin = park_due(2.9, 100.0 + RUNAWAY_PARK_S - 0.5, still, fin)
    assert not due
    assert park_due(2.9, 100.0 + RUNAWAY_PARK_S, still, fin)[0]
    # 정상 정차: PARK_AFTER_S 정지로 끈다
    due, still, fin = park_due(0.1, 200.0, None, None)
    assert not due and still == 200.0
    assert park_due(0.1, 200.0 + PARK_AFTER_S, still, fin)[0]


def test_park_due_is_not_postponed_by_speed_alternating_around_threshold():
    """0.29↔0.31 m/s 교대에도 미션 끝 상한으로 끈다 (2026-10-11 검토: 두 타이머가 서로 지워 60 s 동안 안 끔)."""
    from ugv.drivers.px4 import RUNAWAY_PARK_S, park_due
    still = fin = None
    t, due_at = 0.0, None
    while t < 60.0:
        due, still, fin = park_due(0.31 if int(t * 2) % 2 else 0.29, t, still, fin)
        if due:
            due_at = t
            break
        t += 0.5
    assert due_at is not None and due_at <= RUNAWAY_PARK_S + 1e-9


def test_px4_telemetry_without_velocity_is_not_fresh_standstill():
    """위치만 받고 속도를 못 받았으면 0 m/s 최신 정지가 아니라 나이 무한대 (2026-10-11 검토 재현)."""
    import math as _m
    import time as _t
    from types import SimpleNamespace
    from ugv.drivers.px4 import Px4Driver
    d = Px4Driver.__new__(Px4Driver)
    from ugv.geo import FRAME
    d.frame = FRAME
    d._pos = SimpleNamespace(latitude_deg=38.07, longitude_deg=128.17, absolute_altitude_m=300.0)
    d._pos_mono = _t.monotonic()
    d._vel, d._mono, d._heading, d._armed, d._mode = None, {"position": _t.monotonic()}, 0.0, False, "HOLD"
    tel = d.telemetry()
    assert _m.isinf(tel.age_s()) and tel.armed                 # 속도 없음 → 끊김과 같게, armed 미수신 → 시동 걸림으로
    d._vel = SimpleNamespace(north_m_s=0.0, east_m_s=0.0)
    d._mono.update(velocity=_t.monotonic() - 30.0, armed=_t.monotonic())
    assert d.telemetry().age_s() >= 29.0                       # 오래된 0 m/s 는 최신이 아니다
    d._mono["velocity"] = _t.monotonic()
    tel = d.telemetry()
    assert tel.age_s() < 1.0 and tel.speed_mps == 0.0 and not tel.armed


def test_first_item_ahead_skips_items_passed_during_upload():
    """업로드 동안 지나친 항목은 건너뛴다 (2026-10-11 Gazebo: 첫 항목들이 차 뒤 → 로버 되돌기·도로 이탈)."""
    from ugv.drivers.px4 import first_item_ahead
    sent = [(0.0, 23.0, 9.0, True), (0.0, 6.7, 9.0, True), (0.0, 10.6, 9.0, True), (0.0, 18.1, 9.0, True), (0.0, 42.9, 9.0, True),
            (0.0, 80.0, 9.0, True), (0.0, 120.0, 9.0, False)]
    sent = [(0.0, 5.0, 9.0, True)] + sent[1:]                       # 선행 지점(차 뒤) + 항목들, 북쪽(+y)으로 진행
    k = first_item_ahead(sent, (0.0, 17.0), 9.0)                     # 차는 y 17 — 항목 0~3 은 뒤·밑
    assert sent[k][1] > 17.0 + 3.0 and k == 4
    assert first_item_ahead(sent, (0.0, 4.0), 0.0) == 0              # 아직 첫 항목(선행 지점) 전 — 평소 출발 그대로
    assert first_item_ahead(sent, (200.0, 17.0), 9.0) == 0           # 미션 선에서 멀면 맞추지 않음
