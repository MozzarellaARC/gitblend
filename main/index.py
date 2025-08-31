import os
import hashlib
import json
from typing import Dict, List, Optional, Tuple
import bpy


def _project_root_dir() -> str:
    # Blender relative // points to the .blend directory
    root = bpy.path.abspath("//") or os.getcwd()
    return root


def _index_dir() -> str:
    return os.path.join(_project_root_dir(), ".gitblend")


def get_index_path() -> str:
    # Primary JSON index path (new format)
    return os.path.join(_index_dir(), "index.json")


def _legacy_index_toml_path() -> str:
    # Legacy TOML index path (for backward compatibility reads)
    return os.path.join(_index_dir(), "index.toml")


def _ensure_index_dir():
    os.makedirs(_index_dir(), exist_ok=True)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _fmt_floats(vals, digits: int = 6) -> str:
    return ",".join(f"{float(v):.{digits}f}" for v in vals)


def _matrix_hash(m) -> str:
    vals = []
    try:
        for i in range(4):
            for j in range(4):
                vals.append(m[i][j])
    except Exception:
        pass
    return _sha256(_fmt_floats(vals))


def _list_hash(values: List[str]) -> str:
    return _sha256("|".join(values))


# (TOML escape/writer removed; JSON is used for storage)


def compute_object_signature(obj: bpy.types.Object) -> Dict:
    # L2-ish signature: names/meta + transforms + dims + counts
    sig: Dict = {}
    sig["name"] = obj.name or ""
    sig["parent"] = obj.parent.name if obj.parent else ""
    sig["type"] = obj.type
    # Data block name (helps distinguish reused data)
    try:
        sig["data_name"] = getattr(obj, "data", None).name if getattr(obj, "data", None) else ""
    except Exception:
        sig["data_name"] = ""
    # Transforms and dimensions
    sig["transform"] = _matrix_hash(obj.matrix_world)
    try:
        sig["dims"] = _sha256(_fmt_floats(obj.dimensions))
    except Exception:
        sig["dims"] = ""

    # Materials (all objects that have material_slots)
    try:
        mats = [slot.material.name if slot.material else "" for slot in getattr(obj, "material_slots", [])]
    except Exception:
        mats = []
    sig["materials"] = _list_hash(mats)

    obj_type = getattr(obj, "type", None)
    has_data = getattr(obj, "data", None) is not None

    if obj_type == "MESH" and has_data:
        me = obj.data
        sig["verts"] = int(len(me.vertices))
        # Topology counts
        try:
            sig["edges"] = int(len(me.edges))
        except Exception:
            sig["edges"] = 0
        try:
            sig["polygons"] = int(len(me.polygons))
        except Exception:
            sig["polygons"] = 0
        # Modifiers (type+name order)
        mods = [(m.type, m.name) for m in getattr(obj, "modifiers", [])]
        sig["modifiers"] = _list_hash([f"{t}:{n}" for t, n in mods])
        # Vertex group names
        vgn = [vg.name for vg in getattr(obj, "vertex_groups", [])]
        sig["vgroups"] = _list_hash(sorted(vgn))
        # UV layers names (order)
        uvl = getattr(me, "uv_layers", None)
        uvs = [uv.name for uv in uvl] if uvl else []
        sig["uv_meta"] = _list_hash(uvs)
        # Shapekeys names (order)
        kb = getattr(getattr(me, "shape_keys", None), "key_blocks", None)
        sk = [k.name for k in kb] if kb else []
        sig["shapekeys_meta"] = _list_hash(sk)
        # Shapekey values snapshot (name:value)
        try:
            if kb:
                vals = [f"{k.name}:{float(getattr(k, 'value', 0.0)):.6f}" for k in kb]
            else:
                vals = []
        except Exception:
            vals = []
        sig["shapekeys_values"] = _list_hash(vals)
        # Geometry hash (object-space vertex coordinates)
        try:
            coords = []
            for v in me.vertices:
                co = v.co
                coords.extend((f"{float(co.x):.6f}", f"{float(co.y):.6f}", f"{float(co.z):.6f}"))
            sig["geo_hash"] = _sha256("|".join(coords))
        except Exception:
            sig["geo_hash"] = ""
    elif obj_type == "LIGHT" and has_data:
        # Light-specific meta
        li = obj.data  # bpy.types.Light
        vals = []
        try:
            vals.append(str(getattr(li, "type", "")))
            col = getattr(li, "color", None)
            if col is not None:
                vals.append(_fmt_floats(col))
            vals.append(f"{float(getattr(li, 'energy', 0.0)):.6f}")
            # Common shadow/soft size
            if hasattr(li, "shadow_soft_size"):
                vals.append(f"{float(getattr(li, 'shadow_soft_size', 0.0)):.6f}")
            # Sun angle or Spot specifics
            if hasattr(li, "angle"):
                vals.append(f"{float(getattr(li, 'angle', 0.0)):.6f}")
            if getattr(li, "type", "") == "SPOT":
                vals.append(f"{float(getattr(li, 'spot_size', 0.0)):.6f}")
                vals.append(f"{float(getattr(li, 'spot_blend', 0.0)):.6f}")
            if getattr(li, "type", "") == "AREA":
                vals.append(str(getattr(li, "shape", "")))
                vals.append(f"{float(getattr(li, 'size', 0.0)):.6f}")
                if hasattr(li, "size_y"):
                    vals.append(f"{float(getattr(li, 'size_y', 0.0)):.6f}")
        except Exception:
            pass
        sig["light_meta"] = _sha256("|".join(vals))
        # Fill non-mesh placeholders
        sig["verts"] = 0
        sig["edges"] = 0
        sig["polygons"] = 0
        sig["modifiers"] = ""
        sig["vgroups"] = ""
        sig["uv_meta"] = ""
        sig["shapekeys_meta"] = ""
        sig["shapekeys_values"] = ""
        sig["geo_hash"] = ""
    elif obj_type == "CAMERA" and has_data:
        # Camera-specific meta
        cam = obj.data  # bpy.types.Camera
        vals = []
        try:
            vals.append(str(getattr(cam, "type", "")))
            # Core intrinsics
            for attr in ("lens", "ortho_scale", "sensor_width", "sensor_height",
                         "shift_x", "shift_y", "clip_start", "clip_end"):
                if hasattr(cam, attr):
                    vals.append(f"{float(getattr(cam, attr)):.6f}")
            # Depth of Field
            dof = getattr(cam, "dof", None)
            if dof is not None:
                use_dof = bool(getattr(dof, "use_dof", False))
                vals.append("DOF:1" if use_dof else "DOF:0")
                for attr in ("focus_distance", "aperture_fstop", "aperture_size"):
                    if hasattr(dof, attr):
                        try:
                            vals.append(f"{float(getattr(dof, attr)):.6f}")
                        except Exception:
                            pass
        except Exception:
            pass
        sig["camera_meta"] = _sha256("|".join(vals))
        # Fill non-mesh placeholders
        sig["verts"] = 0
        sig["edges"] = 0
        sig["polygons"] = 0
        sig["modifiers"] = ""
        sig["vgroups"] = ""
        sig["uv_meta"] = ""
        sig["shapekeys_meta"] = ""
        sig["shapekeys_values"] = ""
        sig["geo_hash"] = ""
    else:
        # Other types
        sig["verts"] = 0
        sig["edges"] = 0
        sig["polygons"] = 0
        sig["modifiers"] = ""
        sig["vgroups"] = ""
        sig["uv_meta"] = ""
        sig["shapekeys_meta"] = ""
        sig["shapekeys_values"] = ""
        sig["geo_hash"] = ""

    return sig


def _iter_objects_with_paths(root: bpy.types.Collection):
    """Yield (object, path_list) where path_list is the list of collection names from root's child to the collection holding the object.
    The root collection name is excluded from the path. Objects directly under root have an empty path_list.
    If an object is found in multiple branches, the first encountered path is used.
    """
    # DFS over collections recording path
    seen: set[int] = set()  # object id() seen to avoid duplicates

    def dfs(coll: bpy.types.Collection, path: List[str]):
        nonlocal seen
        for o in coll.objects:
            try:
                oid = id(o)
            except Exception:
                oid = None
            if oid is not None and oid in seen:
                continue
            if oid is not None:
                seen.add(oid)
            yield o, path
        for ch in coll.children:
            ch_name = getattr(ch, "name", "") or ""
            next_path = path + ([ch_name] if ch_name else [])
            yield from dfs(ch, next_path)

    yield from dfs(root, [])


def compute_collection_signature(coll: bpy.types.Collection) -> Tuple[Dict[str, Dict], str]:
    obj_sigs: Dict[str, Dict] = {}
    for obj, path in _iter_objects_with_paths(coll):
        sig = compute_object_signature(obj)
        if not sig["name"]:
            continue
        # Store collection path relative to provided root (exclude root name)
        try:
            # Normalize as 'A|B|C' to avoid ambiguity with '/'
            sig["collection_path"] = "|".join([p for p in path if p])
        except Exception:
            sig["collection_path"] = ""
        obj_sigs[sig["name"]] = sig
    # Overall collection hash: names + per-object quick fields
    parts: List[str] = []
    for nm in sorted(obj_sigs.keys()):
        s = obj_sigs[nm]
        parts.append("|".join([
            nm,
            s.get("parent", ""),
            s.get("type", ""),
            s.get("data_name", ""),
            s.get("transform", ""),
            s.get("dims", ""),
            str(s.get("verts", 0)),
            s.get("modifiers", ""),
            s.get("vgroups", ""),
            s.get("uv_meta", ""),
            s.get("shapekeys_meta", ""),
            s.get("shapekeys_values", ""),
            s.get("materials", ""),
            str(s.get("edges", 0)),
            str(s.get("polygons", 0)),
            s.get("geo_hash", ""),
            s.get("light_meta", ""),
            s.get("camera_meta", ""),
            s.get("collection_path", ""),
        ]))
    collection_hash = _sha256("\n".join(parts))
    return obj_sigs, collection_hash


def _iter_collections_objects(coll: bpy.types.Collection):
    for o in coll.objects:
        yield o
    for c in coll.children:
        yield from _iter_collections_objects(c)


def load_index() -> Dict:
    """Load the Git Blend index, preferring JSON (new), falling back to legacy TOML.
    If TOML is found and parsed, return its data without writing; save_index will persist as JSON on next write.
    """
    json_path = get_index_path()
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"branches": {}}
        if "branches" not in data or not isinstance(data.get("branches"), dict):
            data["branches"] = {}
        return data

    # Fallback: legacy TOML read (best-effort)
    toml_path = _legacy_index_toml_path()
    if os.path.exists(toml_path):
        try:
            # Python 3.11+ stdlib tomllib (optional)
            import tomllib  # type: ignore

            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
            if "branches" not in data or not isinstance(data.get("branches"), dict):
                data["branches"] = {}
            return data
        except Exception:
            pass
    return {"branches": {}}


def save_index(data: Dict) -> None:
    """Save the index as pretty-printed JSON."""
    _ensure_index_dir()
    path = get_index_path()
    # Ensure top-level structure validity
    if not isinstance(data, dict):
        data = {"branches": {}}
    if "branches" not in data or not isinstance(data.get("branches"), dict):
        data["branches"] = {}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        # Best-effort; ignore write failures silently in addon context
        pass


def get_latest_commit(index: Dict, branch: str) -> Optional[Dict]:
    b = (index.get("branches", {})).get(branch)
    if not b:
        return None
    commits = b.get("commits", [])
    if not commits:
        return None
    return commits[-1]


def derive_changed_set(curr_objs: Dict[str, Dict], prev_objs: Dict[str, Dict]) -> Tuple[bool, List[str]]:
    """Return (has_changes, changed_names).
    Includes:
    - Added and removed object names (set differences)
    - Modified objects among the intersection (attribute differences)
    Previously, a name set change would short-circuit and miss modified objects that still exist; this fixes that.
    """
    curr_names = set(curr_objs.keys())
    prev_names = set(prev_objs.keys())

    # Added/removed
    added = curr_names - prev_names
    removed = prev_names - curr_names

    changed_set = set()  # collect as set to avoid dups
    changed_set.update(added)
    changed_set.update(removed)

    # Modified within intersection
    intersect = curr_names & prev_names
    base_keys = (
        "parent",
        "type", "data_name", "transform", "dims", "verts",
        "edges", "polygons",
        "modifiers", "vgroups", "uv_meta", "shapekeys_meta", "shapekeys_values", "materials",
        "geo_hash",
        "light_meta", "camera_meta",
    )
    for nm in intersect:
        a = curr_objs.get(nm, {})
        b = prev_objs.get(nm, {})
        # Compare base keys always
        for k in base_keys:
            if str(a.get(k)) != str(b.get(k)):
                changed_set.add(nm)
                break
        else:
            # Compare collection_path only when present in both (backward compatible)
            if ("collection_path" in a) and ("collection_path" in b):
                if str(a.get("collection_path", "")) != str(b.get("collection_path", "")):
                    changed_set.add(nm)

    changed_list = sorted(changed_set)
    return (len(changed_list) > 0), changed_list


def update_index_with_commit(index: Dict, branch: str, uid: str, timestamp: str, message: str,
                             snapshot_name: str, obj_sigs: Dict[str, Dict], collection_hash: str) -> Dict:
    b = index.setdefault("branches", {}).setdefault(branch, {"head": {}, "commits": []})
    commit_obj_list = []
    for nm in sorted(obj_sigs.keys()):
        commit_obj_list.append(obj_sigs[nm])
    commit = {
        "uid": uid,
        "timestamp": timestamp,
        "message": message,
        "snapshot": snapshot_name,
        "collection_hash": collection_hash,
        "objects": commit_obj_list,
    }
    b["commits"].append(commit)
    b["head"] = {"uid": uid, "snapshot": snapshot_name, "timestamp": timestamp}
    return index
