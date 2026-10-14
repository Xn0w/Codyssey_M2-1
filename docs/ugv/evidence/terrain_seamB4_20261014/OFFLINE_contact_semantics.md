# 접촉 메시지 힘·법선 의미 — 오프라인 대조 (2026-10-14, Codex 1045 1절, Gazebo 없음)
설치 소스 없음 → 같은 버전 상류 원문 (src_check/, SRC_sha1.txt): gz-sim 8.15.0 Physics.cc·Contact.cc, gz-msgs 10.4.0 contact.proto, gz-physics 7.8.0 dartsim SimulationFeatures.cc, DART 6.13.2 Contact.hpp·ContactConstraint.cpp.

| 단계 | 근거 | 의미 |
|---|---|---|
| DART Contact | Contact.hpp 53~69 | `normal` = bodyNode2 → bodyNode1 (월드), `force` = **bodyNode1 에 작용** (월드), body2 는 −force, `penetrationDepth` |
| DART 힘 값 | ContactConstraint.cpp 633~673 | `force = normal·λ_n/dt + D₀·λ_t1/dt + D₁·λ_t2/dt` (법선 + 마찰 두 방향), 마찰 없는 경우 법선만 |
| gz-physics dartsim | SimulationFeatures.cc 262~289 | 접촉점마다 ExtraContactData {force, normal, depth} = DART 값 그대로, collision1/2 = DART collisionObject1/2 |
| gz-sim Physics | Physics.cc 4300~4420 | 같은 접촉점 데이터를 **(coll1→coll2) 와 (coll2→coll1) 양쪽 메시지에 같은 포인터로** 넣음. 메시지 collision1 = 센서 쪽 엔티티, 그러나 `body_1_wrench.force` = DART body1 (엔진 순서) 에 작용하는 힘, body_2 = −force, normal 도 엔진 순서 그대로 → **센서 쪽 바퀴가 엔진 body2 이면 부호 반대**. 점마다 position·normal·wrench·depth 한 개씩 |
| gz-sim Contact | Contact.cc 149~153 | 위 메시지를 그대로 복사 (header stamp 만 추가) |

**기존 기록기 (gz_detail_seam v1) 해석에 주는 영향**
- 바퀴 fz 를 `body_1_wrench.force` 합으로 씀 — 네 바퀴 Σfz ≈ +m·g (15,915 N) 이므로 이번 쌍들에서는 엔진 body1 = 바퀴로 보이나, **쌍마다 보장되지 않음** (Σfz 만으로 모든 축·법선 프레임 검증 아님 — Codex 지적).
- ft/fn = `split_force(ΣF, Σn)`: 한 메시지 안의 점별 법선을 합해 단위화한 평균 법선에 합력을 투영 → **개별 점의 마찰 원뿔 사용률과 같지 않음** (점들이 서로 다른 법선이면 평균 법선이 틀어져 ft 가 커질 수 있음). cn = Contact 묶음 수 (점 수 아님).
- 지형 마찰 μ = 1.0 (타일 SDF). 점 하나·법선이 정확하다면 ft/fn ≈ 1 은 **마찰 원뿔 한계** 를 뜻함 — bR1y 앞바퀴 0.93/1.04 는 한계 근처. 다중 점 평균 효과인지 실제 한계 마찰인지는 점별 원본이 없어 **미확인**.
- depth: VALID 바퀴 대부분 0.0, bR1y FR 만 0.0118 → depth 는 엔진이 제공하는 값 (항상 0 은 아님) — 앞선 '항상 0 (미제공)' 기록은 정정.
- 분석기 note '접촉 상대에 타일 이름 없음' 은 `"T0" in name` 조건 때문에 T16 타일에서 잘못 붙은 주석 (판정에는 영향 없음) — seam_check_c1b.py 에서 `kangwon_tile_T` 로 정정, 원 출력 보존.

**다음 계측 (gz_detail_seam_v3)**: 0.1 s 마다 바퀴별 원본 메시지 — 점별 collision1/2, position, normal, depth, body_1/body_2 force (+ body 이름) — 를 JSONL 로 → 점별 법선 기울기·점별 ft/fn·엔진 body 순서·부호를 직접 계산.
