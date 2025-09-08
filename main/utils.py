import bpy # type: ignore # type: ignore
import os
from datetime import datetime
import re
from typing import Callable, Dict, Optional, Set, Tuple


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


def log_change(props, message: str, branch: str | None = None) -> None:
    """Append a message to the change log safely with branch info."""
    try:
        item = props.changes_log.add()
        item.timestamp = now_str()
        item.message = message
        item.branch = (branch or getattr(props, "gitblend_branch", "") or "").strip() or "main"
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


def iter_objects_recursive(coll: bpy.types.Collection):
    """Recursively iterate through all objects in a collection hierarchy."""
    for o in coll.objects:
        yield o
    for c in coll.children:
        yield from iter_objects_recursive(c)


def get_original_name(id_block) -> str:
    """Get the original name of an object or collection, stripping snapshot suffixes."""
    try:
        v = id_block.get("gitblend_orig_name", None)
        if isinstance(v, str) and v:
            return v
    except Exception:
        pass
    name = getattr(id_block, "name", "") or ""
    # Strip our own _<digits> or _<digits>-<digits> suffix (snapshot naming)
    m = re.search(r"_(\d{10,20})(?:-\d+)?$", name)
    return name[: m.start()] if m else name


def build_name_map(coll: bpy.types.Collection, snapshot: bool = False) -> dict:
    """Build a mapping of names to objects in a collection.
    
    Args:
        coll: Collection to map
        snapshot: If True, use original names from gitblend_orig_name metadata
    
    Returns:
        Dictionary mapping names to objects
    """
    out = {}
    for o in iter_objects_recursive(coll):
        nm = get_original_name(o) if snapshot else (o.name or "")
        if nm and nm not in out:
            out[nm] = o
    return out


def find_containing_collection(root_coll: bpy.types.Collection, target_obj: bpy.types.Object):
    """Find the collection that directly contains the target object.

    Note: membership on bpy_prop_collection expects a name (string),
    not the object reference itself.
    """
    try:
        tname = target_obj.name
    except Exception:
        return None
    if root_coll.objects.get(tname) is not None:
        return root_coll
    for child in root_coll.children:
        found = find_containing_collection(child, target_obj)
        if found:
            return found
    return None


def path_to_collection(root_coll: bpy.types.Collection, target_coll: bpy.types.Collection) -> list:
    """Get the path from root collection to target collection."""
    path = []
    found = False
    
    def dfs(c, acc):
        nonlocal path, found
        if found:
            return
        acc.append(c)
        if c == target_coll:
            path = list(acc)
            found = True
        else:
            for ch in c.children:
                dfs(ch, acc)
                if found:
                    break
        acc.pop()
    
    dfs(root_coll, [])
    return path if found else []


def ensure_mirrored_path(source_coll: bpy.types.Collection, snapshot_path: list) -> bpy.types.Collection:
    """Ensure a mirrored collection path exists under source collection."""
    dest = source_coll
    for snap_coll in snapshot_path[1:]:
        name = get_original_name(snap_coll)
        existing = None
        for ch in dest.children:
            if ch.name == name:
                existing = ch
                break
        if existing is None:
            try:
                newc = bpy.data.collections.new(name)
                dest.children.link(newc)
                dest = newc
            except Exception:
                pass
        else:
            dest = existing
    return dest


def duplicate_object_with_data(obj: bpy.types.Object) -> bpy.types.Object:
    """Create a duplicate of an object including its data."""
    dup = obj.copy()
    if getattr(obj, "data", None) is not None:
        try:
            dup.data = obj.data.copy()
        except Exception:
            pass
    return dup


def remove_object_safely(obj: bpy.types.Object) -> bool:
    """Safely remove an object from all collections and delete it."""
    try:
        for col in list(obj.users_collection):
            try:
                col.objects.unlink(obj)
            except Exception:
                pass
        bpy.data.objects.remove(obj, do_unlink=True)
        return True
    except Exception:
        return False
