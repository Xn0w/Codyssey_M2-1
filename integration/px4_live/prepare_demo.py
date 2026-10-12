# -*- coding: utf-8 -*-
"""integration/px4_live/prepare_demo.py — 새로 클론한 저장소에서 PX4·Gazebo 통합 시연(run_integ.py)에 필요한 생성물을 만든다.

logs/ 는 git 에 올리지 않으므로 클론에는 다음이 없다. 이 도구가 저장소 안 원자료(DEM·도로망)로 다시 만든다.
  - logs/ugv/stage5/tiles/{T03..T05_15..17}/  시연 월드 tz_a33 의 지형 타일 9개 (build_terrain_tiles 기본 설정)
  - logs/ugv/stage5/tiles/tz_a33.sdf, road_subset_tz_a33.json, tiles.json
  - logs/ugv/stage4/single_a_fleet.json        UGV 1대(A-ugv1, PX4 인스턴스 1) 차량 구성
만든 뒤 시연 검증(2026-10-11, 38aa911) 때와 같은 파일인지 sha1 으로 확인한다 (월드 4adb2fe3015b4c0f, 도로 부분집합 2ed984f988d81620).
이미 같은 파일이 있으면 다시 만들지 않는다. 다른 파일이 있으면 덮어쓰지 않고 멈춘다 (--force 로 덮어씀).

사용: .venv/Scripts/python.exe integration/px4_live/prepare_demo.py [--force]
그다음: python integration/px4_live/run_integ.py preflight  (INTEGRATION_README.md 'PX4 실기동 통합 시연' 참고)
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TILES_DIR = ROOT / "logs" / "ugv" / "stage5" / "tiles"
FLEET = ROOT / "logs" / "ugv" / "stage4" / "single_a_fleet.json"
WORLD = "tz_a33"
TILES = ["T03_17", "T04_17", "T05_17", "T03_16", "T04_16", "T05_16", "T03_15", "T04_15", "T05_15"]
EXPECT = {  # 시연 검증 때 파일 sha1 앞 16자리
    f"{WORLD}.sdf": "4adb2fe3015b4c0f",
    f"road_subset_{WORLD}.json": "2ed984f988d81620",
    "T03_17/heightmap.png": "42b8c2f773a1", "T04_17/heightmap.png": "ba66e48596be", "T05_17/heightmap.png": "3423bc30f3dc",
    "T03_16/heightmap.png": "1fda2e49bf77", "T04_16/heightmap.png": "f05ca3bddd4f", "T05_16/heightmap.png": "fd2f47acb88b",
    "T03_15/heightmap.png": "991f59878b23", "T04_15/heightmap.png": "52cbd989df37", "T05_15/heightmap.png": "4d87eba38f49",
}
FLEET_JSON = [{
    "resource_id": "A-ugv1", "resource_type": "UGV", "profile": "adair_ugv", "station_base_id": "A", "station_slot": 0,
    "initial": "STATION", "driver": "px4",
    "px4": {"address": "udpin://0.0.0.0:14541", "instance": 1, "gz_world": "kangwon_flat", "gz_model": "adair_ugv_1"},
}]
# 지형 생성 설정을 바꾸는 환경 변수 — 남아 있으면 시연과 다른 지형이 나오므로 지운다
TERRAIN_ENV = ("ADAIR_TILES_OUT", "ADAIR_JUNCTION_MODE", "ADAIR_JUNC_LEVEL_SIGMA_M", "ADAIR_JUNC_TERRAIN_NODES", "ADAIR_JUNC_DESIGN_NODES",
               "ADAIR_DESIGN_CORE", "ADAIR_DESIGN_GRADE_RULE", "ADAIR_DESIGN_PAINT_CORE", "UGV_ROAD_SUBSET", "UGV_EXTRA_ROADS")


def sha(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()


def check():
    bad = {}
    for rel, want in EXPECT.items():
        p = TILES_DIR / rel
        got = sha(p)[:len(want)] if p.exists() else None
        if got != want:
            bad[rel] = got
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="다른 내용의 기존 파일을 덮어쓴다")
    a = ap.parse_args()
    bad = check()
    present = [r for r, g in bad.items() if g is not None]
    if not bad:
        print("지형: 시연과 같은 파일이 이미 있음")
    elif present and not a.force:
        print("지형: 시연과 다른 파일이 있어 멈춤 (덮어쓰려면 --force):", ", ".join(present))
        sys.exit(1)
    else:
        env = {k: v for k, v in os.environ.items() if k not in TERRAIN_ENV}
        env["PYTHONIOENCODING"] = "utf-8"
        for args in (["--only", ",".join(TILES)], ["--world", WORLD, "--tiles", ",".join(TILES)]):
            r = subprocess.run([sys.executable, "-m", "ugv.tools.build_terrain_tiles", *args], cwd=ROOT, env=env)
            if r.returncode:
                sys.exit(f"build_terrain_tiles {' '.join(args)} 실패 (종료 코드 {r.returncode})")
        bad = check()
        if bad:
            sys.exit(f"지형: 만든 파일이 시연 때와 다름 {bad} — 코드·원자료(environment/data/processed) 버전을 확인")
        print(f"지형: 타일 {len(TILES)}개·{WORLD}.sdf·도로 부분집합 생성, 시연과 같음 ({TILES_DIR})")
    FLEET.parent.mkdir(parents=True, exist_ok=True)
    if FLEET.exists() and json.loads(FLEET.read_text(encoding="utf-8")) != FLEET_JSON and not a.force:
        print(f"차량 구성: 다른 내용이 있어 그대로 둠 (덮어쓰려면 --force): {FLEET}")
        sys.exit(1)
    FLEET.write_text(json.dumps(FLEET_JSON, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"차량 구성: {FLEET}")
    print("다음: python integration/px4_live/run_integ.py preflight")


if __name__ == "__main__":
    main()
