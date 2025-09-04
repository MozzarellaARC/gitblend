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


# Legacy helpers removed: we now always operate on the active scene's root collection


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
# Pointer remapping utilities
# -----------------------------

class NameResolver:
    """Reusable name->Object resolver that prefers primary map over fallback.

    Avoids recreating closures for each remap call.
    """
    def __init__(self, primary: Dict[str, bpy.types.Object], fallback: Dict[str, bpy.types.Object]):
        self.primary = primary or {}
        self.fallback = fallback or {}

    def __call__(self, name: str) -> Optional[bpy.types.Object]:
        try:
            if not name:
                return None
            obj = self.primary.get(name)
            if obj:
                return obj
            return self.fallback.get(name)
        except Exception:
            return None


def _owner_suffix(owner_name: str) -> str:
    try:
        m = re.search(r"\.(\d{3,})$", owner_name or "")
        return m.group(0) if m else ""
    except Exception:
        return ""


def resolve_target_with_variants(owner_name: str, target_obj: Optional[bpy.types.Object], resolver: Callable[[str], Optional[bpy.types.Object]]) -> Optional[bpy.types.Object]:
    """Prefer exact name, then base+owner-suffix, then base name.

    owner_name: name of the object owning the pointer (used for suffix matching)
    target_obj: current referenced object to be remapped
    resolver: callable that maps a name to an Object (new_dups first, then existing)
    """
    try:
        if target_obj is None:
            return None
        # 1) exact
        tname = getattr(target_obj, "name", "") or ""
        if tname:
            hit = resolver(tname)
            if hit:
                return hit
        # 2) base + owner's suffix (e.g., prefer Cube.001 for Sphere.001)
        base = get_original_name(target_obj) or tname
        suf = _owner_suffix(owner_name or "")
        if suf and base:
            cand = f"{base}{suf}"
            hit = resolver(cand)
            if hit:
                return hit
        # 3) base only
        if base:
            hit = resolver(base)
            if hit:
                return hit
        return target_obj
    except Exception:
        return target_obj


def remap_object_pointers(obj: bpy.types.Object, resolver: Callable[[str], Optional[bpy.types.Object]]) -> None:
    """Remap modifier/constraint/driver object pointers using resolver(name)->Object.

    - Modifiers: scan common attributes and all RNA properties; remap any Object value.
    - Constraints: remap .target and any RNA Object pointers.
    - Drivers: remap variable targets whose id is an Object.
    """
    owner_name = getattr(obj, "name", "") or ""
    # Modifiers
    try:
        for m in getattr(obj, "modifiers", []) or []:
            try:
                # Known attributes first
                for ident in ("object", "mirror_object", "offset_object", "target", "curve_object", "auxiliary_target"):
                    try:
                        if hasattr(m, ident):
                            cur = getattr(m, ident)
                            if isinstance(cur, bpy.types.Object):
                                new = resolve_target_with_variants(owner_name, cur, resolver)
                                if new is not None and new is not cur:
                                    setattr(m, ident, new)
                                    # Special-case Mirror: ensure toggle is enabled alongside pointer
                                    if getattr(m, "type", None) == 'MIRROR' and ident == "mirror_object" and hasattr(m, "use_mirror_object"):
                                        try:
                                            m.use_mirror_object = True
                                        except Exception:
                                            pass
                    except Exception:
                        pass
                # Mirror enforcement: ensure toggle is on when a mirror_object exists
                try:
                    if getattr(m, "type", None) == 'MIRROR' and hasattr(m, "use_mirror_object"):
                        if isinstance(getattr(m, "mirror_object", None), bpy.types.Object):
                            try:
                                m.use_mirror_object = True
                            except Exception:
                                pass
                except Exception:
                    pass
                rna = getattr(m, "bl_rna", None)
                if rna:
                    for prop in getattr(rna, "properties", []) or []:
                        try:
                            ident = getattr(prop, "identifier", "")
                            if not ident or ident in {"rna_type", "name"}:
                                continue
                            val = getattr(m, ident, None)
                            if isinstance(val, bpy.types.Object):
                                new = resolve_target_with_variants(owner_name, val, resolver)
                                if new is not None and new is not val:
                                    setattr(m, ident, new)
                        except Exception:
                            continue
                # Geometry Nodes modifier: object-like inputs
                try:
                    if getattr(m, "type", None) == 'NODES':
                        ng = getattr(m, "node_group", None)
                        if ng:
                            for node in getattr(ng, "nodes", []) or []:
                                try:
                                    if hasattr(node, "object") and isinstance(node.object, bpy.types.Object):
                                        new = resolve_target_with_variants(owner_name, node.object, resolver)
                                        if new is not None and new is not node.object:
                                            node.object = new
                                except Exception:
                                    pass
                                for sock in getattr(node, "inputs", []) or []:
                                    try:
                                        if hasattr(sock, "default_value"):
                                            dv = sock.default_value
                                            if isinstance(dv, bpy.types.Object):
                                                new = resolve_target_with_variants(owner_name, dv, resolver)
                                                if new is not None and new is not dv:
                                                    sock.default_value = new
                                    except Exception:
                                        continue
                except Exception:
                    pass
            except Exception:
                continue
    except Exception:
        pass

    # Constraints
    try:
        for c in getattr(obj, "constraints", []) or []:
            try:
                if hasattr(c, "target") and isinstance(c.target, bpy.types.Object):
                    new = resolve_target_with_variants(owner_name, c.target, resolver)
                    if new is not None and new is not c.target:
                        c.target = new
                rna = getattr(c, "bl_rna", None)
                if rna:
                    for prop in getattr(rna, "properties", []) or []:
                        try:
                            ident = getattr(prop, "identifier", "")
                            if not ident or ident in {"rna_type", "name", "target"}:
                                continue
                            val = getattr(c, ident, None)
                            if isinstance(val, bpy.types.Object):
                                new = resolve_target_with_variants(owner_name, val, resolver)
                                if new is not None and new is not val:
                                    setattr(c, ident, new)
                        except Exception:
                            continue
            except Exception:
                continue
    except Exception:
        pass

    # Drivers
    try:
        ad = getattr(obj, "animation_data", None)
        if ad and ad.drivers:
            for fc in ad.drivers:
                try:
                    drv = fc.driver
                    for var in drv.variables:
                        for targ in var.targets:
                            try:
                                idref = getattr(targ, "id", None)
                                if isinstance(idref, bpy.types.Object):
                                    new = resolve_target_with_variants(owner_name, idref, resolver)
                                    if new is not None and new is not idref:
                                        targ.id = new
                            except Exception:
                                continue
                except Exception:
                    continue
    except Exception:
        pass


def remap_references_for_objects(new_dups: Dict[str, bpy.types.Object], existing_by_name: Dict[str, bpy.types.Object]) -> None:
    """Remap object pointers on all provided objects.

    Resolution priority: new_dups[name] first, else existing_by_name[name].
    """
    resolver = NameResolver(new_dups, existing_by_name)

    for obj in (new_dups or {}).values():
        try:
            remap_object_pointers(obj, resolver)
        except Exception:
            continue


# -----------------------------
# Pointer dependency utilities
# -----------------------------

def pointer_targets(obj: bpy.types.Object) -> Set[str]:
    """Return names of objects referenced by modifiers/constraints/drivers/geometry nodes on obj."""
    out: Set[str] = set()
    try:
        # Modifiers
        for m in getattr(obj, "modifiers", []) or []:
            try:
                # Known attributes
                for ident in ("object", "mirror_object", "offset_object", "target", "curve_object", "auxiliary_target"):
                    try:
                        if hasattr(m, ident):
                            tgt = getattr(m, ident)
                            if isinstance(tgt, bpy.types.Object) and getattr(tgt, "name", ""):
                                out.add(tgt.name)
                    except Exception:
                        pass
                # Generic RNA value check
                rna = getattr(m, "bl_rna", None)
                if rna:
                    for prop in getattr(rna, "properties", []) or []:
                        try:
                            ident = getattr(prop, "identifier", "")
                            if not ident or ident in {"rna_type", "name"}:
                                continue
                            val = getattr(m, ident, None)
                            if isinstance(val, bpy.types.Object) and getattr(val, "name", ""):
                                out.add(val.name)
                        except Exception:
                            continue
                # Geometry Nodes
                try:
                    if getattr(m, "type", None) == 'NODES':
                        ng = getattr(m, "node_group", None)
                        if ng:
                            for node in getattr(ng, "nodes", []) or []:
                                try:
                                    if hasattr(node, "object") and isinstance(node.object, bpy.types.Object) and node.object.name:
                                        out.add(node.object.name)
                                except Exception:
                                    pass
                                for sock in getattr(node, "inputs", []) or []:
                                    try:
                                        if hasattr(sock, "default_value"):
                                            dv = sock.default_value
                                            if isinstance(dv, bpy.types.Object) and getattr(dv, "name", ""):
                                                out.add(dv.name)
                                    except Exception:
                                        continue
                except Exception:
                    pass
            except Exception:
                continue
        # Constraints
        for c in getattr(obj, "constraints", []) or []:
            try:
                if hasattr(c, "target") and isinstance(c.target, bpy.types.Object) and getattr(c.target, "name", ""):
                    out.add(c.target.name)
                rna = getattr(c, "bl_rna", None)
                if rna:
                    for prop in getattr(rna, "properties", []) or []:
                        try:
                            ident = getattr(prop, "identifier", "")
                            if not ident or ident in {"rna_type", "name", "target"}:
                                continue
                            val = getattr(c, ident, None)
                            if isinstance(val, bpy.types.Object) and getattr(val, "name", ""):
                                out.add(val.name)
                        except Exception:
                            continue
            except Exception:
                continue
        # Drivers
        ad = getattr(obj, "animation_data", None)
        if ad and ad.drivers:
            for fc in ad.drivers:
                try:
                    drv = fc.driver
                    for var in drv.variables:
                        for targ in var.targets:
                            try:
                                idref = getattr(targ, "id", None)
                                if isinstance(idref, bpy.types.Object) and getattr(idref, "name", ""):
                                    out.add(idref.name)
                            except Exception:
                                continue
                except Exception:
                    continue
    except Exception:
        pass
    return out


def compute_pointer_dependency_closure(curr_objs: Dict[str, bpy.types.Object], initial_changed: Set[str]) -> Tuple[Set[str], Set[str]]:
    """Expand changed names to include referenced targets; also return targets not in curr_objs (external).

    Returns (changed_names, external_deps).
    """
    changed: Set[str] = set(initial_changed)
    external: Set[str] = set()
    if not curr_objs:
        return changed, external
    names_in_src = set(curr_objs.keys())
    stable = False
    while not stable:
        before = len(changed)
        for nm in list(changed):
            try:
                obj = curr_objs.get(nm)
                if not obj:
                    continue
                for dep in pointer_targets(obj):
                    if dep in names_in_src:
                        changed.add(dep)
                    else:
                        external.add(dep)
            except Exception:
                continue
        stable = len(changed) == before
    return changed, external


def remap_scene_pointers(source: bpy.types.Collection, new_dups: Dict[str, bpy.types.Object]) -> None:
    """Convenience: remap object pointers for new duplicates and other objects in a source collection."""
    try:
        existing_by_name = build_name_map(source, snapshot=False)
        resolver = NameResolver(new_dups, existing_by_name)
        # Remap new duplicates first
        for obj in (new_dups or {}).values():
            try:
                remap_object_pointers(obj, resolver)
            except Exception:
                continue
        # Then all other objects in the source collection
        for name, obj in list(existing_by_name.items()):
            if name in new_dups:
                continue
            try:
                remap_object_pointers(obj, resolver)
            except Exception:
                pass
    except Exception:
        pass
