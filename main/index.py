import os
import hashlib
import tomllib
from typing import Dict, List, Optional, Tuple
import bpy


def _project_root_dir() -> str:
    # Blender relative // points to the .blend directory
    root = bpy.path.abspath("//") or os.getcwd()
    return root


def _index_dir() -> str:
    return os.path.join(_project_root_dir(), ".gitblend")


def get_index_path() -> str:
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


def _toml_escape(val) -> str:
    s = "" if val is None else str(val)
    # Escape backslashes and double quotes for TOML basic strings
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return s


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

    # Mesh-specific meta
    if getattr(obj, "type", None) == "MESH" and getattr(obj, "data", None) is not None:
        me = obj.data
        sig["verts"] = int(len(me.vertices))
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
    elif getattr(obj, "type", None) == "LIGHT" and getattr(obj, "data", None) is not None:
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
        sig["modifiers"] = ""
        sig["vgroups"] = ""
        sig["uv_meta"] = ""
        sig["shapekeys_meta"] = ""
    elif getattr(obj, "type", None) == "CAMERA" and getattr(obj, "data", None) is not None:
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
        sig["modifiers"] = ""
        sig["vgroups"] = ""
        sig["uv_meta"] = ""
        sig["shapekeys_meta"] = ""
    else:
        sig["verts"] = 0
        sig["modifiers"] = ""
        sig["vgroups"] = ""
        sig["uv_meta"] = ""
        sig["shapekeys_meta"] = ""

    return sig


def compute_collection_signature(coll: bpy.types.Collection) -> Tuple[Dict[str, Dict], str]:
    obj_sigs: Dict[str, Dict] = {}
    for c in _iter_collections_objects(coll):
        sig = compute_object_signature(c)
        if not sig["name"]:
            continue
        obj_sigs[sig["name"]] = sig
    # Overall collection hash: names + per-object quick fields
    parts: List[str] = []
    for nm in sorted(obj_sigs.keys()):
        s = obj_sigs[nm]
        parts.append("|".join([
            nm,
            s.get("type", ""),
            s.get("data_name", ""),
            s.get("transform", ""),
            s.get("dims", ""),
            str(s.get("verts", 0)),
            s.get("modifiers", ""),
            s.get("vgroups", ""),
            s.get("uv_meta", ""),
            s.get("shapekeys_meta", ""),
            s.get("light_meta", ""),
            s.get("camera_meta", ""),
        ]))
    collection_hash = _sha256("\n".join(parts))
    return obj_sigs, collection_hash


def _iter_collections_objects(coll: bpy.types.Collection):
    for o in coll.objects:
        yield o
    for c in coll.children:
        yield from _iter_collections_objects(c)


def load_index() -> Dict:
    path = get_index_path()
    if not os.path.exists(path):
        return {"branches": {}}
    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except Exception:
            return {"branches": {}}
    if "branches" not in data or not isinstance(data["branches"], dict):
        data["branches"] = {}
    return data


def save_index(data: Dict) -> None:
    _ensure_index_dir()
    path = get_index_path()
    # Minimal TOML writer for our structure
    lines: List[str] = []
    branches = data.get("branches", {})
    for bname, bdata in branches.items():
        head = (bdata or {}).get("head", {})
        if head:
            lines.append(f"[branches.{bname}.head]")
            for k in ("uid", "snapshot", "timestamp"):
                v = head.get(k)
                if v is not None:
                    lines.append(f"{k} = \"{_toml_escape(v)}\"")
            lines.append("")
        commits = (bdata or {}).get("commits", [])
        for c in commits:
            lines.append(f"[[branches.{bname}.commits]]")
            for k in ("uid", "timestamp", "message", "snapshot", "collection_hash"):
                v = c.get(k)
                if v is not None:
                    lines.append(f"{k} = \"{_toml_escape(v)}\"")
            # objects array
            objs = c.get("objects", [])
            for o in objs:
                lines.append(f"[[branches.{bname}.commits.objects]]")
                lines.append(f"name = \"{_toml_escape(o.get('name', ''))}\"")
                lines.append(f"parent = \"{_toml_escape(o.get('parent', ''))}\"")
                lines.append(f"type = \"{_toml_escape(o.get('type', ''))}\"")
                lines.append(f"data_name = \"{_toml_escape(o.get('data_name', ''))}\"")
                lines.append(f"transform = \"{_toml_escape(o.get('transform', ''))}\"")
                lines.append(f"dims = \"{_toml_escape(o.get('dims', ''))}\"")
                lines.append(f"verts = {int(o.get('verts', 0))}")
                lines.append(f"modifiers = \"{_toml_escape(o.get('modifiers', ''))}\"")
                lines.append(f"vgroups = \"{_toml_escape(o.get('vgroups', ''))}\"")
                lines.append(f"uv_meta = \"{_toml_escape(o.get('uv_meta', ''))}\"")
                lines.append(f"shapekeys_meta = \"{_toml_escape(o.get('shapekeys_meta', ''))}\"")
                if o.get('light_meta') is not None:
                    lines.append(f"light_meta = \"{_toml_escape(o.get('light_meta', ''))}\"")
                if o.get('camera_meta') is not None:
                    lines.append(f"camera_meta = \"{_toml_escape(o.get('camera_meta', ''))}\"")
            lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def get_latest_commit(index: Dict, branch: str) -> Optional[Dict]:
    b = (index.get("branches", {})).get(branch)
    if not b:
        return None
    commits = b.get("commits", [])
    if not commits:
        return None
    return commits[-1]


def derive_changed_set(curr_objs: Dict[str, Dict], prev_objs: Dict[str, Dict]) -> Tuple[bool, List[str]]:
    curr_names = set(curr_objs.keys())
    prev_names = set(prev_objs.keys())
    if curr_names != prev_names:
        # any name set change means there are changes
        changed = sorted(list((curr_names - prev_names) | (prev_names - curr_names)))
        return True, changed
    changed_list: List[str] = []
    for nm in curr_names:
        a = curr_objs[nm]
        b = prev_objs.get(nm, {})
        keys = (
            "type", "data_name", "transform", "dims", "verts",
            "modifiers", "vgroups", "uv_meta", "shapekeys_meta",
            "light_meta", "camera_meta",
        )
        for k in keys:
            if (str(a.get(k)) != str(b.get(k))):
                changed_list.append(nm)
                break
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
