# -*- coding: utf-8 -*-
"""항목 7 격리 후보 오프라인 에뮬레이션 (트리 파일 수정 없음, 몽키패치): 3단계 (pair, 3) 를 '방향선 어긋남 ≥ ISO_DEG' 인 회전에만 적용.
어긋남 = 진입·진출 도로의 노드→DIR_LEN_M 점 직선(방향선)과 그 점에서의 도로 접선 각도 차 (turn_mismatch.py 와 같은 정의).
실제 수정안은 approach._plan_approach 가 3단계에 들어가기 전에 이 조건을 보고, 아니면 바로 금지(ban)로 가는 것 — 여기서는 _smooth 에서
(pair,3) 를 무시해 '3단계가 2단계와 같은 결과 → 금지' 로 같은 효과를 낸다 (반복 1회 더 소모, bans 수 불변)."""
import math, os
from ugv import drive_graph as DG

ISO_DEG = float(os.getenv("ISO_DEG", "20"))
FILTERED = []          # (pair, max_mismatch_deg) 3단계가 걸러진 회전
APPLIED = []           # 3단계가 적용된 회전


def _chord_mismatch(net, rid, node, out):
    r = net.roads[rid]
    L = r.length
    d = min(DG.DIR_LEN_M, L)
    n = net.nodes[node]
    s_node = 0.0 if r.a == node else L
    sgn = 1.0 if r.a == node else -1.0
    far = net.at(rid, s_node + sgn * d)
    chord = (far.x - n[0], far.y - n[1])
    cl = math.hypot(*chord) or 1e-9
    chord = (chord[0] / cl, chord[1] / cl)
    q1 = net.at(rid, min(max(s_node + sgn * (d - 1.0), 0.0), L))
    q2 = net.at(rid, min(max(s_node + sgn * (d + 1.0), 0.0), L))
    tan = (q2.x - q1.x, q2.y - q1.y)
    tl = math.hypot(*tan) or 1e-9
    tan = (tan[0] / tl, tan[1] / tl)
    return abs(math.degrees(math.atan2(chord[0] * tan[1] - chord[1] * tan[0], chord[0] * tan[0] + chord[1] * tan[1])))


def pair_mismatch(net, pair):
    (r1, n), (r2, _n2) = pair
    return max(_chord_mismatch(net, r1, n, False), _chord_mismatch(net, r2, n, True))


_orig_smooth = DG.DriveGraph._smooth


def _smooth(self, pts, vlim, legs, relax=frozenset(), sel=None):
    keep = set()
    for x in relax:
        if isinstance(x[1], int) and x[1] == 3:
            m = pair_mismatch(self.net, x[0])
            if m < ISO_DEG:
                FILTERED.append((x[0], round(m, 1)))
                continue
            APPLIED.append((x[0], round(m, 1)))
        keep.add(x)
    return _orig_smooth(self, pts, vlim, legs, frozenset(keep), sel)


DG.DriveGraph._smooth = _smooth
