# -*- coding: utf-8 -*-
"""run_sc_v5 가 시험 시작 전에 부르는 증거 검사 (독립 검증 지적: 저장만이 아니라 기대값 검증·실패 시 거부).
사용: python verify_evidence.py <TAG>   (환경: UGV_MODEL_VARIANT, GZ_MODEL_OVERRIDE, UGV_PX4_STALL_DETECT, SERVER_TREE)
검사: ① server_evidence: STALL_DETECT 값이 요청과 같음(요청 1 이면 has_MISSION_STALL 도 참), 드라이버 모듈 경로가 SERVER_TREE 안
     ② prov: PROVENANCE_OK, 차량마다 model_content_sha1 == 기대 파일(후보 폴더 또는 정식 모델) 내용 해시, 서스펜션 후보면 Gazebo prismatic 4개·아니면 0
     ③ 월드 타일 해시 요약 존재. 하나라도 어긋나면 종료 7 + 이유 출력 (run_sc_v5 가 <TAG>.invalid_evidence 로 남기고 시험 안 함)."""
import hashlib
import json
import os
import sys
from pathlib import Path

G = Path(__file__).resolve().parents[4]   # GitHub 폴더 (형제 작업 트리)
S4 = Path(__file__).resolve().parent
tag = sys.argv[1]
bad = []
want_stall = os.getenv("UGV_PX4_STALL_DETECT", "0") == "1"
srv = os.getenv("SERVER_TREE", "ADAIR_wt_turn")
try:
    ev = json.loads((S4 / f"server_evidence_{tag}.json").read_text(encoding="utf-8").strip().splitlines()[-1])
    if srv not in ev.get("px4_module", ""):
        bad.append(f"서버 드라이버 경로가 {srv} 밖: {ev.get('px4_module')}")
    if want_stall and not (ev.get("STALL_DETECT") is True and ev.get("has_MISSION_STALL")):
        bad.append(f"STALL_DETECT 요청 1 인데 서버 값 {ev.get('STALL_DETECT')} / MISSION_STALL {ev.get('has_MISSION_STALL')}")
    if not want_stall and ev.get("STALL_DETECT") is True:
        bad.append("STALL_DETECT 요청 0 인데 서버 값 참")
except Exception as e:  # noqa: BLE001
    bad.append(f"서버 증거 읽기 실패: {e}")


def sha(p):
    return hashlib.sha1(Path(p).read_bytes().replace(b"\r", b"")).hexdigest()


var = os.getenv("UGV_MODEL_VARIANT", "")
ovr = os.getenv("GZ_MODEL_OVERRIDE", "")
try:
    pv = json.loads((S4 / f"prov_{tag}.json").read_text(encoding="utf-8"))
    st = (S4 / f"prov_{tag}.txt").read_text(encoding="utf-8").strip().splitlines()[-1]
    flat_ok = os.getenv("EVIDENCE_FLAT_WORLD") == "1" and st == "PROVENANCE_INCOMPLETE [] world=True tiles=False"   # 평지: 차량 오류 없음·월드 있음, 타일만 없음
    if not (st.startswith("PROVENANCE_OK") or flat_ok):
        bad.append(f"출처 수집 불완전: {st}")
    if os.getenv("EVIDENCE_FLAT_WORLD") == "1":      # run_flat_ab: 타일 없는 평지 월드 — 월드 파일 해시는 있어야 한다
        if not (pv.get("world") or {}):
            bad.append("월드 출처 없음")
    elif not (pv.get("world") or {}).get("tiles_digest"):
        bad.append("월드 타일 해시 없음")
    for v in pv.get("vehicles", []):
        m = v["model"]
        if m == "x500":
            continue
        if ovr:
            exp = Path(ovr.replace("/mnt/c/", "C:/")) / m / "model.sdf"
        elif var and (G / "ADAIR_wt_vehicle/ugv/gazebo/variants" / var / m / "model.sdf").exists():
            exp = G / "ADAIR_wt_vehicle/ugv/gazebo/variants" / var / m / "model.sdf"
        else:
            exp = G / "ADAIR_wt_vehicle/ugv/gazebo/models" / m / "model.sdf"
        if v.get("model_content_sha1") != sha(exp):
            bad.append(f"{v['resource_id']} 모델 해시 {str(v.get('model_content_sha1'))[:12]} ≠ 기대 {sha(exp)[:12]} ({exp})")
        want_pris = 4 if "<joint name=\"susp_" in exp.read_text(encoding="utf-8") else 0
        if v.get("gz_prismatic_count") != want_pris:
            bad.append(f"{v['resource_id']} Gazebo 서스펜션 관절 {v.get('gz_prismatic_count')} ≠ 기대 {want_pris}")
except Exception as e:  # noqa: BLE001
    bad.append(f"출처 증거 읽기 실패: {e}")
if bad:
    print("EVIDENCE_FAIL " + " | ".join(bad))
    sys.exit(7)
print("EVIDENCE_OK")
