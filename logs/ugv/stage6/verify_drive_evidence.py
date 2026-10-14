# -*- coding: utf-8 -*-
"""run_drive_v2 증거 검사: python verify_drive_evidence.py <prov.json> <후보> <모델> <차량 트리 커밋>
이 실행 ID 의 PX4 환경으로 해석한 model.sdf 내용 해시 == 후보 파일(ugv/gazebo/variants/<후보>/<모델>/model.sdf) 해시,
Gazebo 실제 prismatic 관절 수 == 후보 SDF 의 prismatic 수, PX4 airframe 이 후보 사본이면 그 해시도 기록.
평탄 월드는 지형 타일이 없으므로 tiles_digest 는 보지 않는다 (월드 파일 해시만 기록). 통과하면 EVIDENCE_OK 와 요약 JSON."""
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

VT = Path(__file__).resolve().parents[4] / "ADAIR_wt_vehicle"


def sha1(p):
    return hashlib.sha1(Path(p).read_bytes().replace(b"\r", b"")).hexdigest()


prov_p, var, mdl, commit = sys.argv[1:5]
prov = json.loads(Path(prov_p).read_text(encoding="utf-8"))
f = VT / "ugv/gazebo/variants" / var / mdl / "model.sdf"
want = sha1(f)
want_pris = sum(j.get("type") == "prismatic" for j in ET.fromstring(f.read_text(encoding="utf-8")).find("model").findall("joint"))
af = sorted((VT / "ugv/gazebo/variants" / var / "airframes").glob("*")) if (VT / "ugv/gazebo/variants" / var / "airframes").exists() else []
veh = [v for v in prov.get("vehicles", []) if v.get("model") == mdl]
errs = []
# 코드 커밋 누락 거부 (후속 계획 9313aee 재검토 2): 빈 값·unknown 은 증거 실패
if not commit or commit.strip().lower().startswith("unknown") or len(commit.split("-")[0]) < 7:
    errs.append(f"차량 트리 코드 커밋 없음/불명 ({commit!r})")
if len(veh) != 1:
    errs.append(f"출처 기록 차량 수 {len(veh)}")
else:
    v = veh[0]
    if v.get("error"):
        errs.append(v["error"])
    if v.get("model_content_sha1") != want:
        errs.append(f"모델 해시 {v.get('model_content_sha1')} != 후보 {want}")
    if v.get("gz_prismatic_count") != want_pris:
        errs.append(f"Gazebo prismatic {v.get('gz_prismatic_count')} != 후보 SDF {want_pris}")
summary = {"variant": var, "model": mdl, "vehicle_tree": commit, "model_sha1": want, "prismatic_expected": want_pris,
           "airframes": {a.name: sha1(a) for a in af}, "world": prov.get("world"), "errors": errs}
print(json.dumps(summary, ensure_ascii=False))
print("EVIDENCE_OK" if not errs else f"EVIDENCE_FAIL {errs}")
sys.exit(1 if errs else 0)
