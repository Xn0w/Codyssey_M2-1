"""tiles_v2 → tiles_v2c1 변환 (2026-10-14 사용자 최우선 지시·Codex 0940 C 의 생성기 후보 대신 기존 타일 변환 — 재생성은 tiles_v2 와 바이트 동일하지 않음).
적용 조건 (명시): heightmap PNG N=1025·<sampling> 없음 (기본 1)·collision size X/Y = 1000 — gz-physics 7.8.0 dartsim CustomHeightmapShape (scale = size/vertSize) 보정.
변경: 각 타일 model.sdf 의 collision heightmap size X/Y 만 1000 → 1000·N/(N−1) = 1000.9765625. visual·pose·PNG·수직 size·마찰 불변. PNG 는 복사 (model:// 해석이 같은 폴더를 찾음).
나머지 파일 (tiles.json·월드 SDF·road_subset·static_checks 등) 은 그대로 복사. 사용: python make_tiles_c1.py <tiles_v2> <out>"""
import re, shutil, sys, json
from pathlib import Path
from PIL import Image
S = Path(sys.argv[1]); O = Path(sys.argv[2]); O.mkdir(parents=True, exist_ok=True)
log = {"src": str(S), "changed": [], "skipped": []}
for p in S.iterdir():
    if p.is_file(): shutil.copy2(p, O / p.name)
for d in sorted(x for x in S.iterdir() if x.is_dir() and re.fullmatch(r"T\d\d_\d\d", x.name)):
    od = O / d.name; od.mkdir(exist_ok=True)
    for f in d.iterdir():
        if f.name != "model.sdf": shutil.copy2(f, od / f.name)
    s = (d / "model.sdf").read_text(encoding="utf-8"); N = Image.open(d / "heightmap.png").size
    m = re.search(r'(<collision name="collision"><geometry><heightmap><uri>[^<]+</uri><size>)1000\.000 1000\.000 ([0-9.]+)(</size>)', s)
    if N != (1025, 1025) or "<sampling>" in s or not m:
        log["skipped"].append({"tile": d.name, "N": N, "sampling": "<sampling>" in s, "size_match": bool(m)}); shutil.copy2(d / "model.sdf", od / "model.sdf"); continue
    k = 1000.0 * N[0] / (N[0] - 1)
    s2 = s[:m.start()] + m.group(1) + f"{k:.7f} {k:.7f} {m.group(2)}" + m.group(3) + s[m.end():]
    s2 = s2.replace('<sdf version="1.9">', '<sdf version="1.9">\n  <!-- tiles_v2c1: collision heightmap size X/Y 1000 → 1000·N/(N−1) (gz-physics 7.8.0 scale=size/vertSize 보정, make_tiles_c1.py). visual·높이·pose·PNG 불변 -->', 1)
    (od / "model.sdf").write_text(s2, encoding="utf-8", newline="\n"); log["changed"].append(d.name)
json.dump({**log, "n_changed": len(log["changed"]), "n_skipped": len(log["skipped"])}, open(O / "tiles_c1_transform.json", "w"), indent=1)
print("changed", len(log["changed"]), "skipped", len(log["skipped"]), log["skipped"][:5])
