# -*- coding: utf-8 -*-
"""ugv/version.py — 시험 기록용 실행 버전 정보 (실제로 돌고 있는 코드·설정·자료). 서버 /health 와 시험 도구 기록에 싣는다.
수정 전후가 섞인 기록을 가르려면 커밋만이 아니라 미커밋 변경 해시·실제 서버 작업트리 경로·주요 환경 변수·자료 해시가 필요하다."""

import functools
import hashlib
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(*args, strip=True):
    try:
        out = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=10,
                             encoding="utf-8", errors="replace").stdout
        return out.strip() if strip else out
    except Exception:  # noqa: BLE001
        return None


@functools.lru_cache(maxsize=None)
def file_sha1(path) -> str:
    h = hashlib.sha1()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except OSError:
        return None


@functools.lru_cache(maxsize=None)
def code_info() -> dict:
    """프로세스 시작 시점 코드 (한 번만 — 실행 중 파일이 바뀌어도 시작 때 값)."""
    diff = _git("diff", "HEAD", "--", "ugv", "interfaces", "orchestrator") or ""
    status = _git("status", "--porcelain", "--", "ugv", "interfaces", "orchestrator", strip=False) or ""
    return {"root": str(ROOT), "commit": _git("rev-parse", "HEAD"), "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty_files": [ln[3:] for ln in status.splitlines() if ln.strip()],
            "dirty_diff_sha1": hashlib.sha1(diff.encode("utf-8")).hexdigest()[:16] if diff else None}


def env_info() -> dict:
    return {k: v for k, v in sorted(os.environ.items()) if k.startswith(("UGV_", "PX4_", "GZ_SIM", "ADAIR_"))}
