import bpy
import os
from datetime import datetime


def now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Current timestamp as string."""
    return datetime.now().strftime(fmt)


def request_redraw() -> None:
    """Tag UI areas for redraw so the panel updates immediately."""
    wm = getattr(bpy.context, "window_manager", None)
    if wm:
        for window in wm.windows:
            screen = window.screen
            for area in screen.areas:
                try:
                    area.tag_redraw()
                except Exception:
                    pass
    try:
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    except Exception:
        pass


def get_props(context) -> bpy.types.PropertyGroup | None:
    """Return addon properties from the scene if present."""
    scene = getattr(context, "scene", None)
    return getattr(scene, "gitblend_props", None) if scene else None


def get_selected_branch(props) -> str:
    """Return selected branch based on enum selection.
    Prefers the EnumProperty (selected_string) index; falls back to list index.
    If the selected item's name is empty, return a friendly placeholder (e.g., 'Item 1').
    Only falls back to stored branch or 'main' when no valid selection exists.
    """
    # Determine selected index from enum first, then list index
    idx = -1
    try:
        sel = getattr(props, "selected_string", "")
        if sel not in {"", None, "-1"}:
            idx = int(sel)
    except Exception:
        idx = -1
    if idx < 0:
        try:
            idx = int(getattr(props, "string_items_index", -1))
        except Exception:
            idx = -1

    if 0 <= idx < len(props.string_items):
        nm = (props.string_items[idx].name or "").strip()
        if not nm:
            nm = f"Item {idx+1}"
        return nm

    # No valid selection: use stored default or 'main'
    return (getattr(props, "gitblend_branch", "") or "").strip() or "main"


def find_preferred_or_first_non_dot(scene: bpy.types.Scene, preferred_name: str | None = None) -> bpy.types.Collection | None:
    """Return collection named preferred_name if exists, else first non-.gitblend top-level collection."""
    root = scene.collection
    if preferred_name:
        for c in list(root.children):
            if c.name == preferred_name:
                return c
    for c in list(root.children):
        if c.name != ".gitblend":
            return c
    return None


def ensure_source_collection(scene: bpy.types.Scene) -> bpy.types.Collection:
    """Ensure there's a top-level working collection named 'source' and return it.

    Strategy:
    - If a top-level child named 'source' exists, return it.
    - Else if any collection named 'source' exists in bpy.data, link it under the scene root and return it.
    - Else take the first non-.gitblend top-level collection and rename it to 'source' (if possible).
    - Else create a new collection named 'source' and link it to the scene root.
    """
    root = scene.collection
    # 1) Top-level 'source' already present
    for c in list(root.children):
        if c.name == "source":
            return c
    # 2) A collection named 'source' exists somewhere: ensure it's linked under root
    existing = bpy.data.collections.get("source")
    if existing is not None:
        try:
            # Link under root if not already
            if existing not in root.children:
                root.children.link(existing)
        except Exception:
            pass
        return existing
    # 3) Try to repurpose the first non-.gitblend top-level collection
    first = None
    for c in list(root.children):
        if c.name != ".gitblend":
            first = c
            break
    if first is not None:
        try:
            first.name = "source"
            return first
        except Exception:
            # Fall through to create a new one
            pass
    # 4) Create a new 'source'
    try:
        coll = bpy.data.collections.new("source")
        root.children.link(coll)
        return coll
    except Exception:
        # Last resort: return first non-dot or root.collection
        return first or root


def log_change(props, message: str) -> None:
    """Append a message to the change log safely."""
    try:
        item = props.changes_log.add()
        item.timestamp = now_str()
        item.message = message
    except Exception:
        pass


def ensure_enum_contains(props, value: str) -> None:
    """Ensure the string_items enum contains a value."""
    try:
        if any((it.name or "").strip() == value for it in props.string_items):
            return
        it = props.string_items.add()
        it.name = value
    except Exception:
        pass


def set_dropdown_selection(props, index: int) -> None:
    """Update list index and dropdown selection consistently."""
    props.string_items_index = max(0, min(index, max(0, len(props.string_items) - 1)))
    if len(props.string_items) > 0:
        props.selected_string = str(props.string_items_index)
    else:
        props.selected_string = "-1"


def sanitize_save_path() -> tuple[bool, str, str]:
    """Validate that the .blend is saved and not at a drive root.

    Returns (ok, project_dir, error_msg). If ok is True, project_dir is the folder
    containing the .blend. If False, error_msg contains the reason for failure.
    """
    try:
        blend_path = getattr(bpy.data, "filepath", "") or ""
    except Exception:
        blend_path = ""
    if not blend_path:
        return False, "", "Please save the .blend file first."
    try:
        project_dir = os.path.dirname(os.path.abspath(blend_path))
        drive, _ = os.path.splitdrive(project_dir)
        if drive and os.path.normpath(project_dir) == (drive + os.sep):
            return False, project_dir, "Please save the .blend into a project folder, not the drive root (e.g., C:\\)."
        return True, project_dir, ""
    except Exception:
        return False, "", "Unable to determine project folder from the saved .blend path."
