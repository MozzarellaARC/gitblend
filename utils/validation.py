from __future__ import annotations

import os
import re
from typing import Iterable, List

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover - when imported headless without bpy
    bpy = None  # type: ignore


class ValidationError(RuntimeError):
    pass


BLENDER_EXE_HINT = r"C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe"


def require_saved_blend(context=None) -> str:
    """Ensure the current .blend is saved and return its directory path."""
    if bpy is None:
        raise ValidationError("bpy is not available in this context")
    current_file = bpy.data.filepath
    if not current_file:
        raise ValidationError("Please save the current .blend file first")
    return os.path.dirname(current_file)


def get_dot_gitblend(working_root: str) -> str:
    return os.path.join(working_root, ".gitblend")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def get_addon_root(file_dunder: str) -> str:
    """Given a __file__ inside a subpackage, return the addon root directory."""
    return os.path.dirname(os.path.dirname(file_dunder))


def get_headless_script(addon_root: str, script_name: str) -> str:
    p = os.path.join(addon_root, "headless", script_name)
    if not os.path.exists(p):
        raise ValidationError(f"Headless script missing: {p}")
    return p


def resolve_blender_exe() -> str:
    """Resolve Blender executable path with a hint and bpy fallback."""
    # Prefer the hint, then bpy.app.binary_path
    if os.path.exists(BLENDER_EXE_HINT):
        return BLENDER_EXE_HINT
    try:
        if bpy and getattr(bpy.app, 'binary_path', None):  # type: ignore[attr-defined]
            path = bpy.app.binary_path  # type: ignore[attr-defined]
            if path and os.path.exists(path):
                return path
    except Exception:
        pass
    # Last resort: return hint (will be checked by caller)
    return BLENDER_EXE_HINT


_WS_RE = re.compile(r"\s+")


def sanitize_commit_message(msg: str | None, default_msg: str) -> str:
    if not msg:
        return default_msg
    s = msg.strip()
    # Normalize whitespace
    s = _WS_RE.sub(" ", s)
    # Basic safety: limit length
    return s[:200] if s else default_msg


def normalize_object_names(names: Iterable[str]) -> List[str]:
    out = []
    seen = set()
    for n in names:
        if not n:
            continue
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    out.sort()
    return out


def get_user_commit_message(context) -> str:
    """Return the trimmed commit message from Scene.gitblend_commit_message or empty string."""
    try:
        msg = getattr(context.scene, 'gitblend_commit_message', '') or ''
        return msg.strip()
    except Exception:
        return ''
