"""
Blend I/O utilities for Git Blend.

Exports a copy of the current .blend into the project under .gitblend/blends
so Git LFS can track the binary snapshots alongside lightweight commit metadata.
"""
from __future__ import annotations

import os
import hashlib
from typing import Tuple, Optional


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def export_snapshot_blend(project_dir: str, branch: str, uid: str) -> Tuple[Optional[str], Optional[str]]:
    """Save a copy of the current .blend to .gitblend/blends/<branch>/<branch>_<uid>.blend.

    Returns (abs_path, sha256) if successful, (None, None) otherwise.
    """
    try:
        import bpy # type: ignore  # type: ignore
    except Exception:
        return None, None

    branch_sanitized = (branch or "main").strip() or "main"
    store_dir = os.path.join(project_dir, ".gitblend", "blends", branch_sanitized)
    _ensure_dir(store_dir)

    filename = f"{branch_sanitized}_{uid}.blend"
    abs_path = os.path.abspath(os.path.join(store_dir, filename))

    # Save a copy without switching the current file in Blender
    try:
        res = bpy.ops.wm.save_as_mainfile(filepath=abs_path, copy=True)
        if not (isinstance(res, set) and "FINISHED" in res):
            return None, None
    except Exception:
        return None, None

    try:
        digest = _sha256_file(abs_path)
    except Exception:
        digest = None

    return abs_path, digest
import bpy # type: ignore