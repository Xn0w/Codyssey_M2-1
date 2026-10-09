# ugv/road_point.py — 도로 위 지점 (노드가 아닌 도로 중간에 서기)
#
# 기본 목적지 규칙은 "목표 좌표에서 가장 가까운 도로 노드"다. 교차로 사이 도로가 길면(수백 m~km) 차는 목표에서 먼
# 교차로에 선다. 도로 위 지점 모드는 목표 좌표를 가장 가까운 도로 선형 위의 점으로 내려(투영) 거기서 선다.
#   - 그 도로의 양 끝 노드 중 더 빨리 닿는 쪽까지 경로 탐색 → 그 노드에서 도로를 따라 지점까지 '꼬리 구간'을 덧붙인다
#   - 도착하면 차는 지점에 서 있고 current_node 는 들어온 끝 노드다. 다음 출발은 도로 중간 출발 규칙(agent._leads_from_here)
#   - 같은 지점으로 다시 보내면 움직이지 않고 바로 도착 (붙박이 반복 관측)
#   - 지점이 있는 도로가 막히면 지점에 갈 수 없다 (ROAD_BLOCKED)

from dataclasses import dataclass

from .geo import distance_m, to_latlon, to_ned


@dataclass
class RoadPoint:
    road_id: str
    lat: float
    lon: float
    snap_m: float          # 요청 좌표 ~ 지점 거리
    along_m: float         # 도로 node_a 에서 선형을 따라 지점까지 거리

    def to_dict(self) -> dict:
        return {"road_id": self.road_id, "lat": round(self.lat, 7), "lon": round(self.lon, 7),
                "snap_m": round(self.snap_m, 1), "along_m": round(self.along_m, 1)}


def _line(graph, road) -> list[tuple[float, float]]:
    """도로 선형 node_a → node_b."""
    if road.geometry and len(road.geometry) >= 2:
        return [tuple(p) for p in road.geometry]
    a, b = graph.node(road.node_a), graph.node(road.node_b)
    return [(a.lat, a.lon), (b.lat, b.lon)]


def _project(line, lat, lon) -> tuple[float, int, float, tuple[float, float]]:
    """(거리 m, 구간 번호 i, 구간 안 비율 t, 투영점). 좌표는 요청점 기준 로컬 평면."""
    best = None
    for i, (a, b) in enumerate(zip(line, line[1:])):
        an, ae = to_ned(a[0], a[1], lat, lon)
        bn, be = to_ned(b[0], b[1], lat, lon)
        dn, de = bn - an, be - ae
        seg2 = dn * dn + de * de
        t = 0.0 if seg2 == 0 else max(0.0, min(1.0, -(an * dn + ae * de) / seg2))
        pn, pe = an + t * dn, ae + t * de
        d = (pn * pn + pe * pe) ** 0.5
        if best is None or d < best[0]:
            best = (d, i, t, to_latlon(pn, pe, lat, lon))
    return best


def nearest(graph, lat: float, lon: float) -> RoadPoint | None:
    """좌표에서 가장 가까운 도로 위 점 (막힌 도로 포함 — 막혔으면 판단에서 거절한다)."""
    best = None
    for road in graph.roads():
        line = _line(graph, road)
        d, i, t, p = _project(line, lat, lon)
        if best is None or d < best[0]:
            along = sum(distance_m(x, y) for x, y in zip(line[:i + 1], line[1:i + 1])) + t * distance_m(line[i], line[i + 1])
            best = (d, road, p, along)
    if best is None:
        return None
    d, road, p, along = best
    return RoadPoint(road.road_id, p[0], p[1], d, along)


def tail_leg(graph, rp: RoadPoint, from_node: str, max_speed_mps: float | None) -> dict:
    """끝 노드 from_node 에서 도로를 따라 지점까지 가는 구간 (route_plan 의 leg 형식, to=None·to_point=지점)."""
    road = graph.get_road(rp.road_id)
    line = _line(graph, road)
    cum = [0.0]
    for x, y in zip(line, line[1:]):
        cum.append(cum[-1] + distance_m(x, y))
    if from_node == road.node_a:
        pts = [p for p, c in zip(line, cum) if c < rp.along_m] + [(rp.lat, rp.lon)]
    elif from_node == road.node_b:
        pts = [p for p, c in zip(line, cum) if c > rp.along_m][::-1] + [(rp.lat, rp.lon)]
    else:
        raise ValueError(f"{from_node} 는 도로 {rp.road_id} 의 끝 노드가 아니다")
    if len(pts) == 1:                          # 지점이 끝 노드 바로 위
        n = graph.node(from_node)
        pts = [(n.lat, n.lon)] + pts
    return {"road_id": road.road_id, "from": from_node, "to": None, "to_point": {"lat": rp.lat, "lon": rp.lon},
            "points": pts, "speed_mps": road.speed_mps(max_speed_mps),
            "distance_m": sum(distance_m(a, b) for a, b in zip(pts, pts[1:]))}
