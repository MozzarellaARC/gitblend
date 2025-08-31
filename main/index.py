import os
import hashlib
import json
from typing import Dict, List, Optional, Tuple, Iterable
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


def _bool(v: bool) -> str:
    try:
        return "1" if bool(v) else "0"
    except Exception:
        return "0"


def _id_name(x) -> str:
    try:
        return getattr(x, "name", "") or ""
    except Exception:
        return ""


def _hash_idprops(idblock) -> str:
    """Hash custom ID properties on an ID block, ignoring internal keys.

    Supports simple scalars, sequences and nested dict-like structures.
    """
    items: List[str] = []
    try:
        keys = sorted([k for k in idblock.keys() if isinstance(k, str)])
    except Exception:
        keys = []
    for k in keys:
        if not k or k.startswith("_") or k.startswith("gitblend_"):
            continue
        try:
            v = idblock[k]
        except Exception:
            continue
        def _fmt(v) -> str:
            try:
                if v is None:
                    return "null"
                if isinstance(v, (int, bool)):
                    return str(int(bool(v)) if isinstance(v, bool) else int(v))
                if isinstance(v, float):
                    return f"{float(v):.6f}"
                if isinstance(v, str):
                    return v
                if isinstance(v, dict):
                    return "{" + ",".join(f"{kk}:{_fmt(vv)}" for kk, vv in sorted(v.items())) + "}"
                # Sequence
                try:
                    return "[" + ",".join(_fmt(x) for x in list(v)) + "]"
                except Exception:
                    return str(v)
            except Exception:
                return "?"
        items.append(f"{k}={_fmt(v)}")
    return _sha256("|".join(items))


def _hash_constraints(constraints: Iterable) -> str:
    parts: List[str] = []
    try:
        for c in constraints:
            try:
                tgt = getattr(c, "target", None)
                sub = getattr(c, "subtarget", "")
                parts.append("|".join([
                    str(getattr(c, "type", "")),
                    _id_name(tgt),
                    str(sub or ""),
                    f"{float(getattr(c, 'influence', 0.0)):.6f}",
                ]))
            except Exception:
                pass
    except Exception:
        pass
    return _sha256(";".join(parts))


def _rna_value_repr(owner, prop_ident: str):
    """Return a stable, compact representation for an RNA property value.

    - Pointers -> name
    - Collections -> names or basic value repr joined
    - Numeric/enum/string -> direct
    - Vectors/arrays -> formatted floats
    """
    try:
        val = getattr(owner, prop_ident)
    except Exception:
        return ""
    # Pointer
    try:
        import bpy.types as bt  # type: ignore
        if isinstance(val, bt.ID) or hasattr(val, "name"):
            return _id_name(val)
    except Exception:
        pass
    # Sequence (including mathutils types)
    try:
        if isinstance(val, (list, tuple)):
            return _fmt_floats(val)
    except Exception:
        pass
    # RNA collection
    try:
        it = iter(val)
        # If iter works and not a string
        if isinstance(val, str):
            return val
        names = []
        for item in it:
            nm = _id_name(item)
            if nm:
                names.append(nm)
            else:
                try:
                    names.append(str(item))
                except Exception:
                    names.append("?")
        return ",".join(names)
    except Exception:
        pass
    # Scalars
    try:
        if isinstance(val, (int, bool)):
            return str(int(bool(val)) if isinstance(val, bool) else int(val))
        if isinstance(val, float):
            return f"{float(val):.6f}"
        if isinstance(val, str):
            return val
    except Exception:
        pass
    return str(val)


def _modifiers_meta_hash(obj: bpy.types.Object) -> str:
    parts: List[str] = []
    for m in getattr(obj, "modifiers", []) or []:
        try:
            base = [str(getattr(m, "type", "")), getattr(m, "name", "") or "",
                    _bool(getattr(m, "show_viewport", True)), _bool(getattr(m, "show_render", True))]
            # Special handling for Geometry Nodes
            if getattr(m, "type", "") == 'NODES':
                ng = getattr(m, "node_group", None)
                base.append("NG:" + (_nodes_tree_hash(getattr(ng, "node_tree", ng)) if ng else ""))
                # Also hash exposed inputs (group inputs on modifier)
                try:
                    # Iterate RNA props that start with "Input_" or use interface names
                    # Fallback: scan rna properties writable
                    vals = []
                    for p in m.bl_rna.properties:
                        if p.is_readonly or p.identifier in {"rna_type", "name", "type", "show_viewport", "show_render", "node_group"}:
                            continue
                        vals.append(f"{p.identifier}={_rna_value_repr(m, p.identifier)}")
                    if vals:
                        base.append("GIN:" + _sha256("|".join(sorted(vals))))
                except Exception:
                    pass
            else:
                # Generic property hashing for other modifiers
                vals = []
                for p in m.bl_rna.properties:
                    try:
                        if p.is_readonly:
                            continue
                        pid = p.identifier
                        if pid in {"rna_type", "name", "type", "show_viewport", "show_render"}:
                            continue
                        vals.append(f"{pid}={_rna_value_repr(m, pid)}")
                    except Exception:
                        pass
                if vals:
                    base.append("P:" + _sha256("|".join(sorted(vals))))
            parts.append("/".join(base))
        except Exception:
            pass
    return _sha256(";".join(parts))


def _drivers_hash(idblock) -> str:
    parts: List[str] = []
    try:
        ad = getattr(idblock, "animation_data", None)
        if ad and getattr(ad, "drivers", None):
            for fc in ad.drivers:
                try:
                    drv = getattr(fc, "driver", None)
                    if not drv:
                        continue
                    segs = [getattr(fc, "data_path", "") or "", str(getattr(fc, "array_index", 0))]
                    try:
                        segs.append(getattr(drv, "type", "") or "")
                        segs.append((getattr(drv, "expression", "") or "").strip())
                        vars_parts: List[str] = []
                        for var in getattr(drv, "variables", []) or []:
                            try:
                                tparts: List[str] = [var.name or "", getattr(var, "type", "") or ""]
                                for t in getattr(var, "targets", []) or []:
                                    tparts.extend([
                                        _id_name(getattr(t, "id", None)),
                                        getattr(t, "data_path", "") or "",
                                        getattr(t, "bone_target", "") or "",
                                        getattr(t, "transform_type", "") or "",
                                        getattr(t, "rotation_mode", "") or "",
                                    ])
                                vars_parts.append("[" + ",".join(tparts) + "]")
                            except Exception:
                                pass
                        if vars_parts:
                            segs.append("V:" + ";".join(vars_parts))
                    except Exception:
                        pass
                    parts.append("|".join(segs))
                except Exception:
                    pass
    except Exception:
        pass
    return _sha256("\n".join(parts))


def _nodes_tree_hash(nt) -> str:
    """Hash a node tree structure: nodes (type,name,label), default values, and links."""
    if not nt:
        return ""
    n_parts: List[str] = []
    l_parts: List[str] = []
    try:
        for n in nt.nodes:
            try:
                base = [getattr(n, "bl_idname", "") or getattr(n, "type", ""), getattr(n, "name", "") or "", getattr(n, "label", "") or ""]
                # Include some defaults from inputs if present
                try:
                    in_vals = []
                    for s in getattr(n, "inputs", []) or []:
                        try:
                            if hasattr(s, "default_value"):
                                dv = getattr(s, "default_value")
                                if isinstance(dv, (tuple, list)):
                                    in_vals.append(f"{s.identifier}={_fmt_floats(dv)}")
                                else:
                                    in_vals.append(f"{s.identifier}={str(dv)}")
                        except Exception:
                            pass
                    if in_vals:
                        base.append("IN:" + _sha256("|".join(sorted(in_vals))))
                except Exception:
                    pass
                # Group nodes: include referenced tree name
                try:
                    sub = getattr(n, "node_tree", None)
                    if sub:
                        base.append("SUB:" + _id_name(sub))
                except Exception:
                    pass
                n_parts.append("/".join(base))
            except Exception:
                pass
        for lnk in nt.links:
            try:
                from_id = f"{_id_name(getattr(lnk.from_node, 'name', ''))}:{getattr(lnk.from_socket, 'identifier', '')}"
                to_id = f"{_id_name(getattr(lnk.to_node, 'name', ''))}:{getattr(lnk.to_socket, 'identifier', '')}"
                l_parts.append(f"{from_id}->{to_id}")
            except Exception:
                pass
    except Exception:
        pass
    return _sha256("N:" + _sha256("|".join(n_parts)) + "|L:" + _sha256("|".join(l_parts)))


def _particles_meta_hash(obj: bpy.types.Object) -> str:
    parts: List[str] = []
    try:
        for ps in getattr(obj, "particle_systems", []) or []:
            try:
                st = getattr(ps, "settings", None)
                segs = [getattr(ps, "name", "") or "", _id_name(st)]
                if st is not None:
                    vals = []
                    for attr in ("type", "count", "render_type", "seed", "use_advanced_hair",
                                 "hair_length", "lifetime", "frame_start", "frame_end"):
                        if hasattr(st, attr):
                            try:
                                v = getattr(st, attr)
                                if isinstance(v, float):
                                    vals.append(f"{attr}={float(v):.6f}")
                                else:
                                    vals.append(f"{attr}={str(v)}")
                            except Exception:
                                pass
                    if vals:
                        segs.append("P:" + _sha256("|".join(vals)))
                parts.append("/".join(segs))
            except Exception:
                pass
    except Exception:
        pass
    return _sha256(";".join(parts))


def _geom_nodes_meta_hash(obj: bpy.types.Object) -> str:
    parts: List[str] = []
    try:
        for m in getattr(obj, "modifiers", []) or []:
            if getattr(m, "type", "") == 'NODES':
                try:
                    ng = getattr(m, "node_group", None)
                    parts.append(_nodes_tree_hash(getattr(ng, "node_tree", ng)))
                except Exception:
                    pass
    except Exception:
        pass
    return _sha256("|".join(parts))


def _material_meta_hash(mat) -> str:
    if not mat:
        return ""
    parts: List[str] = []
    try:
        parts.append(getattr(mat, "blend_method", "") or "")
        parts.append(getattr(mat, "shadow_method", "") or "")
        # EEVEE/Cycles common flags
        for attr in ("use_backface_culling", "use_screen_refraction"):
            if hasattr(mat, attr):
                parts.append(f"{attr}={_bool(getattr(mat, attr))}")
        # Node tree
        nt = getattr(mat, "node_tree", None)
        if getattr(mat, "use_nodes", False) and nt is not None:
            parts.append("NT:" + _nodes_tree_hash(nt))
    except Exception:
        pass
    return _sha256("|".join(parts))


def _mesh_uv_and_color_hash(me) -> Tuple[str, str]:
    uv_all: List[str] = []
    col_all: List[str] = []
    # UVs
    try:
        for layer in getattr(me, "uv_layers", []) or []:
            try:
                coords = []
                for d in layer.data:
                    try:
                        coords.append(f"{float(d.uv.x):.5f},{float(d.uv.y):.5f}")
                    except Exception:
                        pass
                uv_all.append(layer.name + "=" + _sha256(";".join(coords)))
            except Exception:
                pass
    except Exception:
        pass
    # Color attributes (corner/point)
    try:
        for attr in getattr(me, "color_attributes", []) or []:
            try:
                vals = []
                for d in attr.data:
                    try:
                        c = getattr(d, "color", None)
                        if c is not None:
                            vals.append(_fmt_floats((c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0), 4))
                    except Exception:
                        pass
                col_all.append(attr.name + "=" + _sha256(";".join(vals)))
            except Exception:
                pass
    except Exception:
        pass
    return _sha256("|".join(uv_all)), _sha256("|".join(col_all))


# (TOML escape/writer removed; JSON is used for storage)


def _ensure_sig_defaults(sig: Dict) -> None:
    """Ensure signature dictionary has all expected keys with defaults.

    This avoids repeating placeholder assignments across object-type branches.
    """
    defaults = {
        "verts": 0,
        "edges": 0,
        "polygons": 0,
    "modifiers": "",
    "modifiers_meta": "",
        "vgroups": "",
        "uv_meta": "",
    "uv_data_hash": "",
    "color_attr_hash": "",
        "shapekeys_meta": "",
        "shapekeys_values": "",
    "shapekeys_points_hash": "",
        "geo_hash": "",
        # Type-specific metas (may remain empty for other types)
        "light_meta": "",
        "camera_meta": "",
        "curve_meta": "",
        "curve_points_hash": "",
        "armature_meta": "",
        "armature_bones_hash": "",
        "pose_bones_hash": "",
    "constraints_hash": "",
    "drivers_hash": "",
    "custom_props_hash": "",
    "visibility_flags": "",
    "materials_meta": "",
    "particles_meta": "",
    "geom_nodes_meta": "",
        # Materials often set above, keep safe default
        "materials": "",
    }
    for k, v in defaults.items():
        if k not in sig:
            sig[k] = v


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

    # Materials (all objects that have material_slots) and meta
    mats: List[str] = []
    mats_meta_parts: List[str] = []
    try:
        for slot in getattr(obj, "material_slots", []) or []:
            try:
                mat = slot.material
                mats.append(mat.name if mat else "")
                mats_meta_parts.append(_material_meta_hash(mat))
            except Exception:
                mats.append("")
                mats_meta_parts.append("")
    except Exception:
        pass
    sig["materials"] = _list_hash(mats)
    sig["materials_meta"] = _sha256("|".join(mats_meta_parts))

    # Base object-level extras
    try:
        sig["constraints_hash"] = _hash_constraints(getattr(obj, "constraints", []) or [])
    except Exception:
        sig["constraints_hash"] = ""
    sig["drivers_hash"] = _drivers_hash(obj)
    sig["custom_props_hash"] = _hash_idprops(obj)
    # Visibility/render flags
    try:
        vis = [
            _bool(getattr(obj, "hide_viewport", False)),
            _bool(getattr(obj, "hide_render", False)),
            _bool(getattr(obj, "visible_get", lambda: True)()),
        ]
        sig["visibility_flags"] = _sha256("|".join(vis))
    except Exception:
        sig["visibility_flags"] = ""

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
        # Modifiers quick list + rich meta
        mods = [(m.type, m.name) for m in getattr(obj, "modifiers", [])]
        sig["modifiers"] = _list_hash([f"{t}:{n}" for t, n in mods])
        sig["modifiers_meta"] = _modifiers_meta_hash(obj)
        # Vertex group names
        vgn = [vg.name for vg in getattr(obj, "vertex_groups", [])]
        sig["vgroups"] = _list_hash(sorted(vgn))
        # UV layers names (order)
        uvl = getattr(me, "uv_layers", None)
        uvs = [uv.name for uv in uvl] if uvl else []
        sig["uv_meta"] = _list_hash(uvs)
        # UV and color data hashes
        uvh, colh = _mesh_uv_and_color_hash(me)
        sig["uv_data_hash"] = uvh
        sig["color_attr_hash"] = colh
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
        # Shapekey points hash (excluding Basis for brevity)
        try:
            if kb:
                pts = []
                for k in kb:
                    nm = (k.name or "").lower()
                    if nm == "basis":
                        continue
                    coords = []
                    for d in getattr(k, "data", []) or []:
                        try:
                            co = getattr(d, "co", None)
                            if co is not None:
                                coords.append(_fmt_floats((co.x, co.y, co.z)))
                        except Exception:
                            pass
                    pts.append(k.name + "=" + _sha256(";".join(coords)))
                sig["shapekeys_points_hash"] = _sha256("|".join(pts))
        except Exception:
            sig["shapekeys_points_hash"] = ""
        # Geometry hash (object-space vertex coordinates)
        try:
            coords = []
            for v in me.vertices:
                co = v.co
                coords.extend((f"{float(co.x):.6f}", f"{float(co.y):.6f}", f"{float(co.z):.6f}"))
            sig["geo_hash"] = _sha256("|".join(coords))
        except Exception:
            sig["geo_hash"] = ""
        # Particle systems and geometry nodes summaries
        sig["particles_meta"] = _particles_meta_hash(obj)
        sig["geom_nodes_meta"] = _geom_nodes_meta_hash(obj)
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
    elif obj_type == "ARMATURE" and has_data:
        arm = obj.data  # bpy.types.Armature
        # Rest armature metadata
        vals = []
        try:
            vals.append(str(getattr(arm, "display_type", "")))
            vals.append(str(getattr(arm, "pose_position", "")))
            vals.append(str(getattr(arm, "deform_method", "")))
        except Exception:
            pass
        sig["armature_meta"] = _sha256("|".join(vals))
        # Bone hierarchy/rest transforms
        try:
            parts = []
            for b in arm.bones:
                try:
                    parts.append("B:" + (b.name or ""))
                    parts.append("P:" + (b.parent.name if b.parent else ""))
                    hl = getattr(b, "head_local", None)
                    tl = getattr(b, "tail_local", None)
                    parts.append("H:" + (_fmt_floats(hl) if hl is not None else ""))
                    parts.append("T:" + (_fmt_floats(tl) if tl is not None else ""))
                    parts.append("Roll:" + f"{float(getattr(b, 'roll', 0.0)):.6f}")
                    parts.append("Conn:" + ("1" if getattr(b, 'use_connect', False) else "0"))
                    parts.append("Deform:" + ("1" if getattr(b, 'use_deform', True) else "0"))
                    parts.append("InheritScale:" + str(getattr(b, 'inherit_scale', "")))
                except Exception:
                    pass
        except Exception:
            parts = []
        sig["armature_bones_hash"] = _sha256("|".join(parts))
        # Pose transforms and a concise constraints summary
        try:
            pparts = []
            pose = getattr(obj, "pose", None)
            if pose is not None:
                for pb in pose.bones:
                    try:
                        pparts.append("PB:" + (pb.name or ""))
                        # Pose matrix in armature space
                        try:
                            pparts.append("Mat:" + _matrix_hash(pb.matrix))
                        except Exception:
                            pass
                        # rotation/location/scale
                        rm = getattr(pb, "rotation_mode", "")
                        pparts.append("RotMode:" + str(rm))
                        try:
                            if rm == 'QUATERNION':
                                q = getattr(pb, "rotation_quaternion", None)
                                if q is not None:
                                    pparts.append("Quat:" + _fmt_floats((q.w, q.x, q.y, q.z)))
                            else:
                                e = getattr(pb, "rotation_euler", None)
                                if e is not None:
                                    pparts.append("Euler:" + _fmt_floats((e.x, e.y, e.z)))
                        except Exception:
                            pass
                        try:
                            loc = getattr(pb, "location", None)
                            if loc is not None:
                                pparts.append("Loc:" + _fmt_floats((loc.x, loc.y, loc.z)))
                        except Exception:
                            pass
                        try:
                            sc = getattr(pb, "scale", None)
                            if sc is not None:
                                pparts.append("Scl:" + _fmt_floats((sc.x, sc.y, sc.z)))
                        except Exception:
                            pass
                        # Constraints summary
                        try:
                            cons = getattr(pb, "constraints", [])
                            cparts = []
                            for c in cons:
                                try:
                                    tgt = getattr(c, "target", None)
                                    sub = getattr(c, "subtarget", "")
                                    cparts.append("|".join([
                                        str(getattr(c, "type", "")),
                                        getattr(tgt, "name", "") if tgt else "",
                                        str(sub or ""),
                                        f"{float(getattr(c, 'influence', 0.0)):.6f}",
                                    ]))
                                except Exception:
                                    pass
                            if cparts:
                                pparts.append("Cons:[" + ";".join(cparts) + "]")
                        except Exception:
                            pass
                    except Exception:
                        pass
        except Exception:
            pparts = []
        sig["pose_bones_hash"] = _sha256("|".join(pparts))
    elif obj_type == "CURVE" and has_data:
        cu = obj.data  # bpy.types.Curve
        # Curve meta (shape and generation)
        vals = []
        try:
            vals.append(str(getattr(cu, "dimensions", "")))
            vals.append(str(getattr(cu, "twist_mode", "")))
            vals.append(f"{float(getattr(cu, 'twist_smoothing', 0.0)):.6f}")
            vals.append(f"{float(getattr(cu, 'resolution_u', 0)):.0f}")
            vals.append(f"{float(getattr(cu, 'resolution_v', 0)):.0f}")
            vals.append(f"{float(getattr(cu, 'render_resolution_u', 0)):.0f}")
            vals.append(f"{float(getattr(cu, 'render_resolution_v', 0)):.0f}")
            vals.append(f"{float(getattr(cu, 'bevel_depth', 0.0)):.6f}")
            vals.append(f"{float(getattr(cu, 'bevel_resolution', 0)):.0f}")
            vals.append(f"{float(getattr(cu, 'extrude', 0.0)):.6f}")
            vals.append(str(getattr(cu, "fill_mode", "")))
            vals.append(str(getattr(cu, "bevel_mode", "")))
            bev = getattr(cu, "bevel_object", None)
            vals.append(getattr(bev, "name", "") if bev else "")
            tp = getattr(cu, "taper_object", None)
            vals.append(getattr(tp, "name", "") if tp else "")
        except Exception:
            pass
        sig["curve_meta"] = _sha256("|".join(vals))
        # Control points hash
        try:
            parts = []
            for sp in cu.splines:
                st = getattr(sp, "type", "")
                parts.append(f"T:{st}")
                # Common attributes per spline
                try:
                    parts.append(f"CyclicU:{int(getattr(sp, 'use_cyclic_u', False))}")
                    parts.append(f"CyclicV:{int(getattr(sp, 'use_cyclic_v', False))}")
                    parts.append(f"OrderU:{int(getattr(sp, 'order_u', 0))}")
                    parts.append(f"OrderV:{int(getattr(sp, 'order_v', 0))}")
                    parts.append(f"ResU:{int(getattr(sp, 'resolution_u', 0))}")
                    parts.append(f"ResV:{int(getattr(sp, 'resolution_v', 0))}")
                except Exception:
                    pass
                if st == 'BEZIER':
                    for bp in getattr(sp, 'bezier_points', []) or []:
                        try:
                            hl = bp.handle_left
                            co = bp.co
                            hr = bp.handle_right
                            parts.extend([
                                _fmt_floats((hl.x, hl.y, hl.z)),
                                _fmt_floats((co.x, co.y, co.z)),
                                _fmt_floats((hr.x, hr.y, hr.z)),
                            ])
                        except Exception:
                            pass
                else:
                    for p in getattr(sp, 'points', []) or []:
                        try:
                            co = p.co  # 4D
                            parts.append(_fmt_floats((co.x, co.y, co.z, co.w)))
                        except Exception:
                            pass
        except Exception:
            parts = []
        sig["curve_points_hash"] = _sha256("|".join(parts))
    elif obj_type in {"EMPTY", "LATTICE", "SURFACE", "META", "FONT", "POINTCLOUD", "VOLUME", "GPENCIL"}:
        # Minimal metas for non-mesh/non-curve types; still include constraints/drivers/idprops/visibility/materials
        try:
            # For empties: display type/size and instance info
            if obj_type == "EMPTY":
                parts = [str(getattr(obj, "empty_display_type", "")), f"{float(getattr(obj, 'empty_display_size', 0.0)):.6f}"]
                if getattr(obj, "instance_type", ""):
                    parts.append("IT:" + str(getattr(obj, "instance_type")))
                    inst = getattr(obj, "instance_collection", None)
                    parts.append("IC:" + _id_name(inst))
                sig["curve_meta"] = _sha256("|".join(parts))
        except Exception:
            pass
    # Ensure all default fields exist
    _ensure_sig_defaults(sig)

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
            s.get("modifiers_meta", ""),
            s.get("vgroups", ""),
            s.get("uv_meta", ""),
            s.get("uv_data_hash", ""),
            s.get("color_attr_hash", ""),
            s.get("shapekeys_meta", ""),
            s.get("shapekeys_values", ""),
            s.get("shapekeys_points_hash", ""),
            s.get("materials", ""),
            s.get("materials_meta", ""),
            str(s.get("edges", 0)),
            str(s.get("polygons", 0)),
            s.get("geo_hash", ""),
            s.get("light_meta", ""),
            s.get("camera_meta", ""),
            s.get("collection_path", ""),
            s.get("curve_meta", ""),
            s.get("curve_points_hash", ""),
            s.get("armature_meta", ""),
            s.get("armature_bones_hash", ""),
            s.get("pose_bones_hash", ""),
            s.get("constraints_hash", ""),
            s.get("drivers_hash", ""),
            s.get("custom_props_hash", ""),
            s.get("visibility_flags", ""),
            s.get("particles_meta", ""),
            s.get("geom_nodes_meta", ""),
        ]))
    collection_hash = _sha256("\n".join(parts))
    return obj_sigs, collection_hash


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
        "modifiers", "modifiers_meta", "vgroups", "uv_meta", "uv_data_hash", "color_attr_hash",
        "shapekeys_meta", "shapekeys_values", "shapekeys_points_hash", "materials", "materials_meta",
        "geo_hash",
        "light_meta", "camera_meta",
        "curve_meta", "curve_points_hash",
        "armature_meta", "armature_bones_hash", "pose_bones_hash",
        "constraints_hash", "drivers_hash", "custom_props_hash", "visibility_flags",
        "particles_meta", "geom_nodes_meta",
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
