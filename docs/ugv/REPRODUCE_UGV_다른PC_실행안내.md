# UGV 시험 — 다른 PC 에서 실행하기 (2026-10-14)

## 필요한 저장소·브랜치 (같은 상위 폴더에 나란히)
| 폴더 | 브랜치 | 역할 |
|---|---|---|
| `ADAIR` | `feat/orchestrator-final` | 실행 스크립트·판정기·지형 타일·증거 문서 (`logs/ugv/…` 필수 파일, `docs/ugv/…`) |
| `ADAIR_wt_hook` | `wip/park-ops` (5dc1af4) | UGV 서버 코드 (운영 정차 설정 `UGV_PX4_PARK_STILL_S` 포함) |
| `ADAIR_wt_vehicle` | `wip/vehicle-susp` (48f3e5f) | 차량 모델 변형 (`susp_a_acc3_imu500` 등)·PX4/Gazebo 기동 도구 |
```
git clone https://github.com/sujinpark50-gif/ADAIR.git ADAIR && cd ADAIR && git checkout feat/orchestrator-final
git worktree add ../ADAIR_wt_hook wip/park-ops
git worktree add ../ADAIR_wt_vehicle wip/vehicle-susp
```
Windows + Git Bash + WSL Ubuntu-24.04 (gz-sim 8.15.0, gz-physics 7.8.0, PX4-Autopilot SITL), Windows `ADAIR/.venv` (rasterio 등). env 파일 (`.env`) 은 저장소에 없음 — 각 PC 에서 따로 준비.

## 저장소에 올린 `logs/ugv` 필수 파일 (logs/ 는 .gitignore — 필수만 강제 추가)
- `logs/ugv/stage4/*.sh`, `verify_evidence.py` — 실행 래퍼 (run_sc_v9 / v10_ops / v11_c1 …)
- `logs/ugv/stage6/**` 의 `.sh`·`.py`·기준 문서·동결 해시·스폰/차량 설정 (`*_spawn.txt`, `*_fleet.json`)·경로/스폰 계산 JSON·logger_topics.txt·상류 소스 사본 (`terrain_ab/src_check/`)
- `logs/ugv/stage5/tiles_v2/` — 메타데이터 (tiles.json·월드 SDF 20 개·road_subset_*.json) + 타일 (heightmap.png·model.sdf·model.config)
- 수정 후보 타일 사본 `terrain_ab/seamC/tiles_c1`, `terrain_ab/seamB4/tiles_c1b4`
- 실행 결과 (CSV·ULog·JSONL·로그) 는 올리지 않음 — 핵심 결과는 `docs/ugv/evidence/*` 에 사본.
- **tiles_v2 616 타일 전체** 와 평지 월드 타일 (tiles_flat·tiles_flathm) 도 올림 (db15ea7). 생성기 재생성은 현재 tiles_v2 와 바이트 동일하지 않음 (2026-10-14 T04_16·T05_16 확인) — 그래서 원본 그대로 보관. 이전 판 tiles·tiles_level 은 미포함.

## 절대 경로 해결 (스크립트 수정 없이, 동결 해시 유지)
1. Windows 관리자 PowerShell: `powershell -ExecutionPolicy Bypass -File tools\setup_other_pc\setup_paths_windows.ps1` → `C:\Users\수다쟁이고양이들` 를 실제 사용자 폴더로 잇는 junction (WSL `/mnt/c/Users/수다쟁이고양이들` 157 곳·Git Bash `/c/Users/…` 2 곳 해결). 파일은 UTF-8 BOM (PowerShell 5.1 한글 경로용).
2. WSL: `bash tools/setup_other_pc/setup_paths_wsl.sh [PX4 폴더]` → `/home/geumsoni/PX4-Autopilot` 링크 (17 곳 해결, sudo).
3. 새로 만드는 스크립트는 환경 변수 (예: ADAIR_ROOT, PX4_DIR) 방식으로 작성 권장.

## 주의
- 많은 스크립트가 **이 PC 의 절대 경로** (`/mnt/c/Users/수다쟁이고양이들/Documents/GitHub/…`, `C:/Users/…`, WSL `/home/geumsoni/PX4-Autopilot`) 를 씀 → 다른 PC 는 같은 경로 구성으로 두거나 경로를 바꿔야 함.
- 동결 해시 (`*_freeze.sha1`) 는 줄바꿈 (LF) 기준 — Git 의 CRLF 변환으로 체크아웃되면 해시 불일치로 체인이 HOLD 할 수 있음 → `git config core.autocrlf false` 권장.
