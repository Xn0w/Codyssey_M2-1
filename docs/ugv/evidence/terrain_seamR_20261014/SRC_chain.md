# 높이장 충돌 전달식 — 설치 버전 상류 소스 확인 (2026-10-14 09:2x, Codex 0905 1절, Gazebo 없음)

설치 (WSL dpkg): gz-sim 8.15.0, gz-physics 7.8.0 (dartsim 플러그인), DART 6.13.2 (libdart-core+collisions+odelcpsolver), libode 0.16.2, gz-common 5.9.0, sdformat 14.9.0. **설치 소스는 없음** → 같은 버전 태그의 공식 상류 원문을 받아 대조 (terrain_ab/src_check/, 해시 SRC_sha1.txt). 설치 바이너리 증거 = 서버 로그 `ODE Heightfield AABB` 160 줄 (verbose 디버그, OdeHeightmap 생성자에서 출력).

| 단계 | 파일 (태그) | 식 | 이번 값 (1025 px PNG, size 1000) |
|---|---|---|---|
| SDF | sdformat14_14.9.0 sdf/1.9/heightmap_shape.sdf (타일 model.sdf 는 sdf 1.9), src/Heightmap.cc | `<sampling>` 기본 1 (타일 SDF 에 없음) | sampling = 1 |
| gz-sim | gz-sim8_8.15.0 src/systems/physics/Physics.cc 1596~1675 | 이미지 → ImageHeightmap, `AttachHeightmapShape(..., Size(), Sampling())` | size (1000, 1000, span), sampling 1 |
| gz-physics | gz-physics7_7.8.0 dartsim/src/CustomHeightmapShape.cc 38~58 | `vertSize = W·s − s + 1`; **`scale.x = size.x / vertSize`**; `FillHeightMap(s, vertSize, …)`; `setHeightField(vertSize, vertSize, h)`; `setScale(scale.x, scale.y, 1)` | vertSize 1025, scale.x = 1000/1025 = **0.975610** (격자 간격으로는 1000/1024 = 0.976563 이어야 함) |
| gz-common | gz-common5_5.9.0 geospatial/include/.../ImageHeightmap.hh FillHeights | 꼭짓점 (x, y) 높이 = 영상 (x/s, y/s) 쌍선형 × scale.z | s=1 → 꼭짓점 i 높이 = 픽셀 i (높이값 자체는 정확) |
| DART | dart v6.13.2 dart/collision/ode/detail/OdeHeightmap-impl.hpp | `dGeomHeightfieldDataBuild*(…, (width−1)·scale.x, (height−1)·scale.y, width, height, scale.z, 0, HF_THICKNESS, 0)`; AABB 를 dtdbg 로 출력 | ODE 폭 = 1024 × 0.975610 = **999.0244 m** |
| ODE | ode 0.16.2 ode/src/heightfield.cpp 145·159·552 | `m_fHalfWidth = fWidth/2`; `m_fSampleWidth = fWidth/(n−1)`; 기하 중심 기준 (−HalfWidth 이동) | 반폭 **499.512195 m** (로그 499.512 와 일치), 표본 간격 0.975610 |

**결과 (소스 수준에서 닫힘)**: 충돌 꼭짓점 i 의 국소 x = −499.512195 + 0.975610·i, 높이 = 픽셀 i. 분석기·시각면의 픽셀 i 위치 = −500 + 0.976563·i. 차이 = +0.487805 − 0.000953·i → 가장자리에서 **중심 쪽으로 0.4878 m 당겨짐**, 중심 (i=512) 0. 인접 타일 사이 **충돌면 없는 띠 0.975610 m** (Codex 정정값; 0.977 은 대략 1 격자 표현). 같은 지점의 높이 차는 국소 경사 × 이동량 (Fable H4: 경로상 최대 ≈ 2.5 cm).
- 확인 안 된 것: 띠 안에서의 ODE 처리 (heightfield 경계 밖 = 충돌 없음이 상류 코드상 기대 동작이나, 다른 충돌체가 메우는지는 R0/R1 접촉 상대 기록으로 확인), HF_THICKNESS 의 실제 값·아래쪽 닫힘 (관통 뒤 갇힘 기전), DART 접촉 복원 속도. AABB 출력은 heightfield geom (회전 뒤) 의 월드 AABB 가 아니라 geom 자체 위치 (body 에 붙기 전) 기준으로 보임 — 수평 반폭만 사용.
- 수정 후보 비교는 하지 않음 (Codex 0905 4절 — 원인 확정 뒤 별도).
