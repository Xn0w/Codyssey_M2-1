# -*- coding: utf-8 -*-
"""
integration/uav_launcher.py
===========================
김동현님의 UAV Local Agent(uav/uav-agent, FastAPI)를 UAV 1대 = 프로세스 1개 = 포트 1개
구조 그대로 서브프로세스로 띄운다. 각 서버는 UAV_MODE=mock(MockDrone)이라 PX4/Gazebo가
필요 없다. 서버가 준비되면 config.UAV_ENDPOINTS를 채우고 UAV_CONNECTION_MODE='real'로 바꾼다.

→ 이렇게 하면 이원규님의 실제 HTTP 커넥터(_send_uav_command_real 등)와
  김동현님의 실제 evaluate/execute 로직이 진짜 HTTP로 붙는다(인프로세스 재구현 아님).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

import config

_REPO_ROOT = Path(__file__).resolve().parent.parent
_UAV_DIR = _REPO_ROOT / "uav" / "uav-agent"

# 띄울 UAV: 재평가(REJECT→다른 후보) 시연을 위해 base A에 2대
_UAV_PLAN = [
    ("A-uav1", 8000),
    ("A-uav2", 8001),
]

_procs: list[subprocess.Popen] = []


def _wait_health(url: str, timeout_s: float = 25.0) -> bool:
    if requests is None:
        return False
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = requests.get(f"{url}/health", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def start() -> list[str]:
    """UAV 서버들을 띄우고 준비된 resource_id 목록을 반환. config를 real 모드로 전환."""
    if requests is None:
        print("[UAV] requests 미설치 → UAV 서버 연동 생략(UAV는 mock 유지). "
              "pip install requests 후 다시 실행하면 실제 HTTP 연동이 켜집니다.")
        return []

    started = []
    # 실행 기록(UAV-01)은 파일에 남는다. 이 통합 실행은 TASK_001 부터 다시 세므로 실행마다 새 폴더를 준다
    # (같은 키·다른 내용 = 409 충돌 규칙에 이전 실행 기록이 걸리지 않게).
    state_dir = _REPO_ROOT / "logs" / "uav_state" / time.strftime("%Y%m%d-%H%M%S")
    for uav_id, port in _UAV_PLAN:
        env = dict(os.environ, UAV_ID=uav_id, UAV_MODE="mock", UAV_STATE_DIR=str(state_dir))
        log = open(_REPO_ROOT / "logs" / f"uav_{uav_id}.log", "w")
        p = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1",
             "--port", str(port), "--log-level", "warning"],
            cwd=str(_UAV_DIR), env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        _procs.append(p)
        url = f"http://127.0.0.1:{port}"
        if _wait_health(url):
            config.UAV_ENDPOINTS[uav_id] = url
            started.append(uav_id)
            print(f"[UAV] {uav_id} 준비됨 → {url} (MockDrone)")
        else:
            print(f"[UAV] {uav_id} 기동 실패(포트 {port}). logs/uav_{uav_id}.log 확인")

    if started:
        config.UAV_CONNECTION_MODE = "real"   # 이원규님 실제 HTTP 커넥터 경로 사용
    return started


def force_reject(uav_id: str, reason: str = "failsafe") -> None:
    """시나리오 재현용 — 특정 UAV를 REJECT 상태로 만든다(/mock/set)."""
    if requests is None:
        return
    url = config.UAV_ENDPOINTS.get(uav_id)
    if not url or url == "TBD":
        return
    params = {"failsafe": True} if reason == "failsafe" else {"battery_pct": 5.0}
    try:
        requests.post(f"{url}/mock/set", params=params, timeout=3)
    except Exception:
        pass


def wait_idle(uav_ids, timeout_s: float = 60.0) -> dict:
    """UAV 가 임무·복귀를 마치고 착륙(대기)할 때까지 기다린다. 돌려주는 값: {uav_id: 기다린 초 또는 None(시간 초과)}.

    UAV 는 복귀 중 재배정을 하지 않는다(uav-agent config.RETASK_WHILE_RETURNING 기본 0 — 총괄 방침).
    통합 실행의 스텝 간격이 Mock 복귀 비행보다 짧으면 다음 Task 가 모두 BUSY 로 거절돼, 재평가 시연(A-uav2 인계)
    대신 후보 없음 실패가 이어진다. 그래서 정책은 그대로 두고 시연 스크립트가 착륙을 기다린다."""
    out = {}
    if requests is None:
        return out
    t0 = time.time()
    deadline = t0 + timeout_s
    for uav_id in uav_ids:
        url = config.UAV_ENDPOINTS.get(uav_id)
        out[uav_id] = None
        if not url or url == "TBD":
            continue
        while True:       # 기한이 지나도 한 번은 조회한다 (앞 드론이 기한을 다 써도 뒤 드론을 시간 초과로 잘못 보고하지 않게)
            try:
                s = requests.get(f"{url}/uav/{uav_id}/state", timeout=3).json()
                if s.get("current_task_id") is None and s.get("returning_task_id") is None and not s.get("armed"):
                    out[uav_id] = round(time.time() - t0, 1)
                    break
            except Exception:
                pass
            if time.time() >= deadline:
                break
            time.sleep(0.5)
    return out


def stop() -> None:
    for p in _procs:
        try:
            p.terminate()
        except Exception:
            pass
    for p in _procs:
        try:
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    _procs.clear()
