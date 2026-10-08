# ugv/route_alt.py — 2순위 경로 (도로 AI 가 비교할 대안)
#
# 1순위 = 지금 도로 상태로 가장 빠른 경로 (Dijkstra, road_graph.find_route).
# 2순위 = Yen 의 k-최단 경로를 짧은 순으로 보다가 1순위와 겹치는 도로 길이가 OVERLAP_MAX(70%) 미만인 첫 경로.
#        거의 같은 길(교차로 하나만 다른 길)은 '대안'으로 의미가 없어서 건너뛴다. K_MAX 개까지 봐도 없으면 None.
# Yen 의 갈래 탐색은 도로를 실제로 막지 않고 '이번 탐색에서만 못 쓰는 도로·노드' 집합으로 한다 — 도로 상태를
# 건드리지 않으므로 별도 스레드에서 돌려도 시나리오 차단과 섞이지 않는다.

import heapq
from dataclasses import dataclass

OVERLAP_MAX = 0.7
K_MAX = 40           # 산간 도로망은 거의 같은 길이 많아 8개로는 겹침 70% 미만 대안이 잘 안 나온다 (설악로 시연: 34번째)


@dataclass
class RouteOption:
    path: list[str]          # 노드 id, 출발 노드 포함
    travel_s: float          # 지금 도로 상태 기준 통과 시간 합 (시뮬레이션 초)
    distance_m: float
    roads: list[str]         # 지나는 도로 id 순서

    def overlap_with(self, other: "RouteOption", graph) -> float:
        """이 경로 길이 중 other 와 같은 도로가 차지하는 비율 (0~1)."""
        if self.distance_m <= 0:
            return 1.0
        shared = set(self.roads) & set(other.roads)
        return sum(graph.get_road(r).distance_m for r in shared) / self.distance_m


def option_of(graph, path: list[str], max_speed_mps: float | None) -> RouteOption | None:
    roads, t, d = [], 0.0, 0.0
    for a, b in zip(path, path[1:]):
        try:
            r = graph.road_between(a, b)
        except KeyError:
            return None
        s = r.travel_s(max_speed_mps)
        if s == float("inf"):
            return None
        roads.append(r.road_id)
        t += s
        d += r.distance_m
    return RouteOption(path=list(path), travel_s=t, distance_m=d, roads=roads)


def _shortest(graph, start: str, goal: str, max_speed_mps, banned_roads: set, banned_nodes: set):
    """막힌 도로 + banned 를 빼고 Dijkstra. (통과시간, 노드 경로) 또는 None."""
    dist, prev, heap = {start: 0.0}, {}, [(0.0, start)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist.get(u, float("inf")):
            continue
        if u == goal:
            path = [goal]
            while path[-1] != start:
                path.append(prev[path[-1]])
            return d, path[::-1]
        for v, road in graph.neighbors(u):
            if road.road_id in banned_roads or v in banned_nodes:
                continue
            nd = d + road.travel_s(max_speed_mps)
            if nd == float("inf"):
                continue
            if nd < dist.get(v, float("inf")):
                dist[v], prev[v] = nd, u
                heapq.heappush(heap, (nd, v))
    return None


def best_and_alternative(graph, start: str, goal: str, max_speed_mps: float | None = None,
                         overlap_max: float = OVERLAP_MAX, k_max: int = K_MAX
                         ) -> tuple[RouteOption | None, RouteOption | None]:
    """(1순위, 2순위). 1순위가 없으면 (None, None). 2순위 조건을 만족하는 경로가 없으면 2순위 None."""
    first = graph.find_route(start, goal, max_speed_mps)
    if not first.reachable:
        return None, None
    best = option_of(graph, first.path, max_speed_mps)
    if best is None or len(best.path) < 2:
        return best, None
    accepted = [best]
    candidates: list[RouteOption] = []
    seen = {tuple(best.path)}
    while len(accepted) < k_max:
        last = accepted[-1].path
        for i in range(len(last) - 1):
            spur, root = last[i], last[:i + 1]
            banned_roads = {graph.road_between(p.path[i], p.path[i + 1]).road_id
                            for p in accepted if p.path[:i + 1] == root and len(p.path) > i + 1}
            found = _shortest(graph, spur, goal, max_speed_mps, banned_roads, set(root[:-1]))
            if found is None:
                continue
            path = root[:-1] + found[1]
            if tuple(path) in seen:
                continue
            seen.add(tuple(path))
            opt = option_of(graph, path, max_speed_mps)
            if opt is not None:
                candidates.append(opt)
        if not candidates:
            break
        candidates.sort(key=lambda o: o.travel_s)
        nxt = candidates.pop(0)
        if nxt.overlap_with(best, graph) < overlap_max:
            return best, nxt
        accepted.append(nxt)
    return best, None
