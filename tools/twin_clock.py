# -*- coding: utf-8 -*-
"""디지털 트윈 시계 — 진짜 세계(환경 계약 서버)를 진행시키는 **유일한** 주체 (INT-05: 시계 소유자 하나).

    python tools/twin_clock.py                # 100배속: /advance 한 번 = subtick_s(트윈 60 s) → 실제 0.6초 (끄면 CA 2100 s → 21초)
    python tools/twin_clock.py --speed 1      # 실시간 (PX4 real 비행과 같은 시간 축)

배속은 드론 쪽 시간과 맞춰야 한다. uav-agent mock 은 MOCK_TIME_SCALE=100 배속으로 날기 때문에 기본값도 100.
PX4 real 로 날리면 --speed 1 (또는 Gazebo 실시간 배속에 맞춘 값)을 쓴다.

총괄이 LLM 을 기다리는 동안(/health llm.in_flight > 0)은 진행하지 않는다 (사용자 결정 2026-10-08). 100배속에서
LLM 60초가 시뮬레이션 1시간 40분이 되어, 실제 운용보다 불이 훨씬 더 번진 뒤에야 계획이 나오는 왜곡을 막는다.
끄기: --no-llm-pause. 총괄이 응답하지 않으면 멈추지 않고 진행한다.
주의: 드론·UGV mock 은 각자 실제 시각으로 움직이므로 시계가 멈춘 동안에도 비행·주행은 계속된다.
"""
import argparse
import time

import httpx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="http://127.0.0.1:8300")
    ap.add_argument("--speed", type=float, default=100.0, help="시뮬레이션 초 / 실제 초")
    ap.add_argument("--until-h", type=float, default=32.25, help="시나리오 시작 후 몇 시간까지 (기상청 자료 끝 = 32.25)")
    ap.add_argument("--orch", default="http://127.0.0.1:8200", help="총괄 주소 (LLM 기다리는 동안 멈춤)")
    ap.add_argument("--no-llm-pause", action="store_true", help="LLM 을 기다려도 멈추지 않는다")
    a = ap.parse_args()
    cx = httpx.Client(timeout=30)
    h = cx.get(f"{a.env}/health").json()
    # 단계 사이 채우기(ENV_SUBTICK_S)가 켜져 있으면 /advance 한 번 = subtick 초 (개인 저장소 ADAIR 와 같음, 2026-10-16)
    tick = h["assumptions"].get("subtick_s") or h["assumptions"]["tick_s"]
    print(f"run {h['run_id']} · 한 번 진행 {tick:.0f}s (CA 단계 {h['assumptions']['tick_s']:.0f}s) · "
          f"{a.speed:g}배속 → 실제 {tick / a.speed:.1f}s 마다 진행")
    # 다음 진행 시각을 시작 시각 기준으로 정한다 — 매번 tick/speed 를 쉬면 조회·진행에 쓴 시간만큼 늦어져
    # 1분 진행(0.6 s 간격)에서 실제 배속이 약 94배로 떨어진다 (2026-10-16). LLM 대기로 멈춘 시간은 기준에서 뺀다
    t0, n = time.monotonic(), 0
    s = cx.get(f"{a.env}/snapshot").json()
    while s["simulation_time_s"] < a.until_h * 3600:
        n += 1
        time.sleep(max(0.0, t0 + n * tick / a.speed - time.monotonic()))
        if not a.no_llm_pause:
            t0 += _wait_llm(cx, a.orch)        # 실제로 멈춘 시간만 뺀다 (상태 조회 시간은 다음 대기에서 흡수)
        late = time.monotonic() - (t0 + n * tick / a.speed)
        if late > 10 * tick / a.speed:            # 10번 넘게 밀리면(절전·오래 멈춤) 몰아서 진행하지 않고 기준을 다시 잡는다
            t0 += late
        s = cx.post(f"{a.env}/advance", json={"steps": 1}).json()
        burning = sum(1 for c in s["fire_cells"] if c["fire_state"] == "BURNING")
        print(f"  sim {s['simulation_time_s'] / 3600:5.2f}h  v{s['state_version']}  타는 칸 {burning:4d}  "
              f"바람 {s['wind_ms']} m/s {s['wind_dir_deg']:.0f}°")
    print("시나리오 끝")


def _wait_llm(cx, orch) -> float:
    """총괄이 LLM 을 기다리는 동안 진행하지 않는다. 총괄이 응답하지 않으면 바로 진행. 돌려주는 값: 멈춘 초 (안 멈췄으면 0)."""
    paused = None
    while True:
        try:
            # 가벼운 경로 (/health 는 판단 화면 요약까지 실어 무겁다 — 2026-10-19)
            busy = cx.get(f"{orch}/llm/in_flight", timeout=5).json().get("in_flight")
        except (httpx.HTTPError, ValueError):
            busy = 0
        if not busy:
            if paused is None:
                return 0.0
            waited = time.monotonic() - paused
            print(f"  LLM 응답 — 시계 다시 진행 (멈춘 시간 {waited:.0f}s)")
            return waited
        if paused is None:
            paused = time.monotonic()
            print("  총괄 LLM 대기 중 — 시계 멈춤")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
