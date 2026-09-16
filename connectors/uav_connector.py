# -*- coding: utf-8 -*-
"""
connectors/uav_connector.py
==============================
UAV Connector (Contract 7번 "UAV Connector"):
- UAV 상태 제공
- Task/명령 전달
- Local 수행가능성 응답 반환
- 관측 및 실행 결과 반환

[참고] 김동현님 공유 이슈: 공유 우분투 서버 방식이 유력하므로
UAV_SERVER_URL을 config에서 분리해 나중에 연결 방식만 교체 가능하게 함.
"""

import random
import config
from interfaces.schema import ResourceStatus, LocalResponse, Observation


def get_uav_status(base: str) -> list:
    if config.UAV_CONNECTION_MODE == "mock":
        return _get_uav_status_mock(base)
    raise NotImplementedError("UAV 실제 연동이 아직 구현되지 않았습니다.")


def send_uav_command(task_id: str, assignment, force_response: str = None, force_reason: str = None) -> LocalResponse:
    """
    force_response/force_reason: 테스트(IT-01/IT-02)에서 특정 응답을 강제하기 위한 훅.
    실제 운영에서는 사용하지 않는다.
    """
    if config.UAV_CONNECTION_MODE == "mock":
        return _send_uav_command_mock(assignment, force_response, force_reason)
    raise NotImplementedError("UAV 실제 명령 전송이 아직 구현되지 않았습니다.")


def get_uav_observation(resource_id: str, timestamp: float, task_id: str = None, decision_id: str = None) -> Observation:
    if config.UAV_CONNECTION_MODE == "mock":
        return Observation(
            resource_id=resource_id,
            location_lat=config.BASE_A_LAT,
            location_lon=config.BASE_A_LON,
            timestamp=timestamp,
            observation_type="FIRE_BOUNDARY",
            value={"note": "mock observation"},
            task_id=task_id,
            decision_id=decision_id,
        )
    raise NotImplementedError("UAV 실제 관측 결과 반환이 아직 구현되지 않았습니다.")


def _get_uav_status_mock(base: str) -> list:
    """거점당 UAV 2대 (Contract 자원 구조 반영: A/B 거점 각 UAV 2대)"""
    base_lat = config.BASE_A_LAT if base == "A" else config.BASE_B_LAT
    base_lon = config.BASE_A_LON if base == "A" else config.BASE_B_LON

    statuses = []
    for i in range(1, 3):
        statuses.append(
            ResourceStatus(
                resource_id=f"{base}-uav{i}",
                resource_type="UAV",
                base=base,
                location_lat=base_lat + random.uniform(-0.01, 0.01),
                location_lon=base_lon + random.uniform(-0.01, 0.01),
                state="READY",
                capability={
                    "battery_pct": round(random.uniform(30, 100), 1),
                    "eta_sec": round(random.uniform(60, 600), 1),
                    "px4_failsafe": False,
                },
                comm_status=random.choice(["OK", "OK", "OK", "WEAK"]),
            )
        )
    return statuses


def _send_uav_command_mock(assignment, force_response, force_reason) -> LocalResponse:
    if force_response is not None:
        return LocalResponse(resource_id=assignment.resource_id, response=force_response, reason=force_reason)

    response = random.choices(["ACCEPT", "REJECT"], weights=[0.8, 0.2])[0]
    reason = None
    if response == "REJECT":
        reason = random.choice(["LOW_BATTERY", "HIGH_WIND", "SENSOR_FAILURE"])
    return LocalResponse(resource_id=assignment.resource_id, response=response, reason=reason)