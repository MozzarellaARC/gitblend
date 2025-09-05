import bpy
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


# -----------------------------
# Pointer Remapping
# -----------------------------

def _find_replacement_object(target_name: str, new_objects: Dict[str, bpy.types.Object], 
                           existing_objects: Dict[str, bpy.types.Object], 
                           requesting_obj: Optional[bpy.types.Object] = None) -> Optional[bpy.types.Object]:
    """Find replacement object, preferring new objects over existing ones.
    
    Args:
        target_name: Name of object to find
        new_objects: Recently restored/created objects
        existing_objects: Objects that were already in the scene
        requesting_obj: The object that needs this reference (for smarter mapping)
    """
    if not target_name:
        return None
    
    # 1. Direct match in new objects first (restored/duplicated objects)
    if target_name in new_objects:
        return new_objects[target_name]
    
    # 2. Try to find by original name in new objects (for gitblend snapshot objects)
    for obj in (new_objects or {}).values():
        try:
            orig_name = obj.get("gitblend_orig_name", "")
            if orig_name and orig_name == target_name:
                return obj
        except Exception:
            pass
    
    # 3. Smart duplicate handling: if requesting object is a duplicate (e.g., "Cube.001")
    # and target is the base name (e.g., "Cube"), prefer a restored base object
    if requesting_obj:
        requesting_name = requesting_obj.name
        requesting_base = get_original_name_from_string(requesting_name)
        target_base = get_original_name_from_string(target_name)
        
        # If requesting object is a duplicate (.001, .002, etc.) looking for base object
        if (requesting_name != requesting_base and target_name == target_base and 
            requesting_base == target_base):
            # Look for the base object in new_objects (restored objects) first
            if target_base in new_objects:
                return new_objects[target_base]
    
    # 4. Handle Blender's duplicate naming pattern (e.g., Cube -> Cube.001, Cube.002)
    # If target is a base name like "Cube", prefer any restored version in new_objects
    base_target_name = get_original_name_from_string(target_name)
    if base_target_name == target_name:  # target_name is already a base name
        # Look for any duplicates of this base name in new_objects first
        for name, obj in (new_objects or {}).items():
            if name.startswith(target_name + ".") and len(name) > len(target_name) + 1:
                suffix = name[len(target_name)+1:]
                if suffix.isdigit() or (suffix.count('.') == 2 and all(part.isdigit() for part in suffix.split('.'))):
                    return obj
            # Also check gitblend_orig_name for duplicates
            try:
                orig_name = obj.get("gitblend_orig_name", "")
                if orig_name and (orig_name == target_name or 
                                (orig_name.startswith(target_name + ".") and 
                                 len(orig_name) > len(target_name) + 1)):
                    suffix = orig_name[len(target_name)+1:]
                    if suffix.isdigit() or (suffix.count('.') == 2 and all(part.isdigit() for part in suffix.split('.'))):
                        return obj
            except Exception:
                pass
    
    # 5. Fall back to existing objects
    if target_name in existing_objects:
        return existing_objects[target_name]
    
    # 6. Try to find by original name in existing objects
    for obj in (existing_objects or {}).values():
        try:
            orig_name = obj.get("gitblend_orig_name", "")
            if orig_name and orig_name == target_name:
                return obj
        except Exception:
            pass
    
    # 7. Last resort: try base name variations
    if base_target_name != target_name:
        # Try the base name
        if base_target_name in new_objects:
            return new_objects[base_target_name]
        if base_target_name in existing_objects:
            return existing_objects[base_target_name]
    
    return None


def get_original_name_from_string(name: str) -> str:
    """Extract original name by removing various suffixes (snapshots, duplicates, etc.)."""
    if not name:
        return ""
    
    # Remove snapshot naming suffixes like _20231201120000 or _20231201120000-1
    import re
    m = re.search(r"_(\d{10,20})(?:-\d+)?$", name)
    if m:
        return name[:m.start()]
    
    # Remove Blender duplicate suffixes like .001, .002, etc.
    # Also handle complex duplicates like .001.001
    m = re.search(r"\.(\d{3})(?:\.(\d{3}))*$", name)
    if m:
        return name[:m.start()]
    
    return name


def remap_object_pointers(obj: bpy.types.Object, new_objects: Dict[str, bpy.types.Object], 
                        existing_objects: Dict[str, bpy.types.Object]) -> None:
    """Simplified pointer remapping focusing on the most common cases."""
    
    # Remap parent relationship
    try:
        if obj.parent:
            parent_name = obj.parent.name
            # Also try original name if it exists
            try:
                parent_orig_name = obj.parent.get("gitblend_orig_name", "")
                if parent_orig_name:
                    parent_name = parent_orig_name
            except Exception:
                pass
            
            new_parent = _find_replacement_object(parent_name, new_objects, existing_objects, obj)
            if new_parent and new_parent != obj.parent:
                obj.parent = new_parent
    except Exception:
        pass
    
    # Remap common modifier object references
    try:
        for modifier in obj.modifiers:
            # Mirror modifier
            if modifier.type == 'MIRROR' and hasattr(modifier, 'mirror_object'):
                if modifier.mirror_object:
                    target_name = _get_reference_name(modifier.mirror_object)
                    new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                    if new_target:
                        modifier.mirror_object = new_target
                        modifier.use_mirror_object = True
            
            # Array modifier
            elif modifier.type == 'ARRAY' and hasattr(modifier, 'offset_object'):
                if modifier.offset_object:
                    target_name = _get_reference_name(modifier.offset_object)
                    new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                    if new_target:
                        modifier.offset_object = new_target
            
            # Boolean modifier (add this common case)
            elif modifier.type in ['BOOLEAN', 'INTERSECT', 'UNION', 'DIFFERENCE'] and hasattr(modifier, 'object'):
                if modifier.object:
                    target_name = _get_reference_name(modifier.object)
                    new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                    if new_target:
                        modifier.object = new_target
            
            # Armature modifier
            elif modifier.type == 'ARMATURE' and hasattr(modifier, 'object'):
                if modifier.object:
                    target_name = _get_reference_name(modifier.object)
                    new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                    if new_target:
                        modifier.object = new_target
            
            # Curve modifier
            elif modifier.type in ['CURVE', 'FOLLOW_PATH'] and hasattr(modifier, 'object'):
                if modifier.object:
                    target_name = _get_reference_name(modifier.object)
                    new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                    if new_target:
                        modifier.object = new_target
    except Exception:
        pass
    
    # Remap constraint targets (simplified)
    try:
        for constraint in obj.constraints:
            if hasattr(constraint, 'target') and constraint.target:
                target_name = _get_reference_name(constraint.target)
                new_target = _find_replacement_object(target_name, new_objects, existing_objects, obj)
                if new_target:
                    constraint.target = new_target
    except Exception:
        pass


def _get_reference_name(target_obj: bpy.types.Object) -> str:
    """Get the best name to use for finding a replacement object."""
    if not target_obj:
        return ""
    
    # Try original name first (for gitblend snapshot objects)
    try:
        orig_name = target_obj.get("gitblend_orig_name", "")
        if orig_name:
            return orig_name
    except Exception:
        pass
    
    # For regular objects, use current name
    # But also consider if this object might be from the gitblend scene
    current_name = target_obj.name or ""
    
    # If the target object is in a gitblend scene, we probably want to find 
    # the corresponding object in the current working set
    try:
        if target_obj.users_scene:
            for scene in target_obj.users_scene:
                if scene.name == "gitblend":
                    # This object is from the gitblend scene, so we want to find
                    # the corresponding object in the main scene
                    # Remove any snapshot suffixes to get the base name
                    return get_original_name_from_string(current_name)
    except Exception:
        pass
    
    return current_name


def remap_references_for_objects(new_objects: Dict[str, bpy.types.Object], 
                               existing_objects: Dict[str, bpy.types.Object]) -> None:
    """Remap object pointers on all provided objects (simplified)."""
    
    for obj in (new_objects or {}).values():
        try:
            remap_object_pointers(obj, new_objects, existing_objects)
        except Exception:
            continue


# -----------------------------
# Dependency Detection
# -----------------------------

def get_object_dependencies(obj: bpy.types.Object) -> Set[str]:
    """Get names of objects that this object depends on (simplified version)."""
    dependencies = set()
    
    # Parent dependency
    try:
        if obj.parent:
            dependencies.add(obj.parent.name)
    except Exception:
        pass
    
    # Modifier dependencies (most common cases)
    try:
        for modifier in obj.modifiers:
            if modifier.type == 'MIRROR' and hasattr(modifier, 'mirror_object'):
                if modifier.mirror_object:
                    dependencies.add(modifier.mirror_object.name)
            elif modifier.type == 'ARRAY' and hasattr(modifier, 'offset_object'):
                if modifier.offset_object:
                    dependencies.add(modifier.offset_object.name)
            elif modifier.type == 'ARMATURE' and hasattr(modifier, 'object'):
                if modifier.object:
                    dependencies.add(modifier.object.name)
            elif modifier.type in ['CURVE', 'FOLLOW_PATH'] and hasattr(modifier, 'object'):
                if modifier.object:
                    dependencies.add(modifier.object.name)
    except Exception:
        pass
    
    # Constraint dependencies
    try:
        for constraint in obj.constraints:
            if hasattr(constraint, 'target') and constraint.target:
                dependencies.add(constraint.target.name)
    except Exception:
        pass
    
    return dependencies


def remap_scene_pointers(source: bpy.types.Collection, new_objects: Dict[str, bpy.types.Object]) -> None:
    """Simplified scene pointer remapping."""
    try:
        existing_objects = build_name_map(source, snapshot=False)
        
        # Remap pointers in new objects
        for obj in (new_objects or {}).values():
            try:
                remap_object_pointers(obj, new_objects, existing_objects)
            except Exception:
                continue
        
        # Remap pointers in existing objects (excluding the new ones to avoid double-processing)
        for name, obj in list(existing_objects.items()):
            if name not in new_objects:
                try:
                    remap_object_pointers(obj, new_objects, existing_objects)
                except Exception:
                    pass
    except Exception:
        pass
