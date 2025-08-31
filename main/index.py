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


# Legacy TOML support removed; JSON is the only supported index format


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


def _ensure_sig_defaults(sig: Dict) -> None:
    """Ensure signature dictionary has all expected keys with defaults.

    This avoids repeating placeholder assignments across object-type branches.
    """
    defaults = {
        "verts": 0,
        "edges": 0,
        "polygons": 0,
        "modifiers": "",
        "vgroups": "",
    # Modifiers
        "uv_meta": "",
        "shapekeys_meta": "",
        "shapekeys_values": "",
        "geo_hash": "",
    # New: stable hash of modifier settings for each modifier
    "modifiers_meta": "",
        # Type-specific metas (may remain empty for other types)
        "light_meta": "",
        "camera_meta": "",
        "curve_meta": "",
        "curve_points_hash": "",
        "armature_meta": "",
        "armature_bones_hash": "",
        "pose_bones_hash": "",
        # Materials often set above, keep safe default
        "materials": "",
        # New generalized metadata fields
        "materials_meta": "",
        "constraints_hash": "",
        "idprops_hash": "",
        "visibility_hash": "",
        "drivers_hash": "",
        "particles_meta": "",
        "geom_nodes_hash": "",
        "uv_data_hash": "",
        "color_attr_hash": "",
        "shapekeys_points_hash": "",
        # Empties / instancing
        "empty_meta": "",
        # Other object-type metas
        "lattice_meta": "",
        "surface_meta": "",
        "metaball_meta": "",
        "font_meta": "",
        "pointcloud_meta": "",
        "volume_meta": "",
        "grease_pencil_meta": "",
    }
    for k, v in defaults.items():
        if k not in sig:
            sig[k] = v


# =====================
# Generic hash helpers
# =====================

def _serialize_scalar(v) -> str:
    try:
        if isinstance(v, float):
            return f"{float(v):.6f}"
        if isinstance(v, (int, bool)):
            return str(int(v))
        if isinstance(v, (bytes, bytearray)):
            return v.decode("utf-8", errors="ignore")
        return str(v)
    except Exception:
        return ""


def _hash_id_properties(idblock) -> str:
    parts: List[str] = []
    try:
        # Avoid Blender internal UI helper dict
        for k in sorted([kk for kk in idblock.keys() if kk != "_RNA_UI"]):  # type: ignore[call-arg]
            try:
                v = idblock[k]
            except Exception:
                continue
            if isinstance(v, (list, tuple)):
                vals = []
                for x in list(v)[:256]:
                    vals.append(_serialize_scalar(x))
                parts.append(f"{k}:[{','.join(vals)}]")
            elif isinstance(v, dict):
                # Shallow dict
                kv = [f"{sk}:{_serialize_scalar(sv)}" for sk, sv in sorted(v.items())]
                parts.append(f"{k}:{{{','.join(kv)}}}")
            else:
                parts.append(f"{k}:{_serialize_scalar(v)}")
    except Exception:
        pass
    return _sha256("|".join(parts))


def _hash_pointer_value(val) -> str:
    # Prefer name for ID datablocks, else str()
    try:
        nm = getattr(val, "name", None)
        if isinstance(nm, str):
            return nm
    except Exception:
        pass
    return _serialize_scalar(val)


def _hash_rna_properties(obj) -> str:
    """Hash a subset of RNA properties, including POINTER/COLLECTION by name/count.
    Skips common noisy props.
    """
    parts: List[str] = []
    try:
        SKIP = {"name", "type", "rna_type", "bl_rna"}
        for p in obj.bl_rna.properties:  # type: ignore[attr-defined]
            try:
                pid = getattr(p, "identifier", "")
            except Exception:
                pid = ""
            if not pid or pid in SKIP:
                continue
            try:
                if getattr(p, "is_hidden", False) or getattr(p, "is_readonly", False):
                    continue
            except Exception:
                pass
            ptype = getattr(p, "type", None)
            try:
                if ptype == "POINTER":
                    v = getattr(obj, pid)
                    parts.append(f"{pid}:{_hash_pointer_value(v)}")
                    continue
                if ptype == "COLLECTION":
                    coll = getattr(obj, pid)
                    # Include up to 16 names deterministically if items have name
                    names: List[str] = []
                    try:
                        for i, it in enumerate(coll):
                            if i >= 16:
                                break
                            nm = getattr(it, "name", None)
                            if isinstance(nm, str):
                                names.append(nm)
                    except Exception:
                        pass
                    parts.append(f"{pid}:count={len(coll)};names={','.join(sorted(names))}")
                    continue
            except Exception:
                pass
            try:
                val = getattr(obj, pid)
            except Exception:
                continue
            if callable(val):
                continue
            try:
                if hasattr(val, "__len__") and not isinstance(val, (str, bytes)):
                    # small sequences only
                    seq = None
                    try:
                        seq = [val[i] for i in range(min(len(val), 16))]
                    except Exception:
                        pass
                    if seq is not None:
                        sval = []
                        for x in seq:
                            sval.append(_serialize_scalar(x))
                        parts.append(f"{pid}:[{','.join(sval)}]")
                        continue
            except Exception:
                pass
            parts.append(f"{pid}:{_serialize_scalar(val)}")
    except Exception:
        pass
    return _sha256("|".join(sorted(parts)))


def _hash_constraints(constraints: Iterable) -> str:
    parts: List[str] = []
    try:
        for c in constraints or []:
            try:
                segs = [str(getattr(c, "type", ""))]
                # Common target-ish fields
                tgt = getattr(c, "target", None)
                segs.append(_hash_pointer_value(tgt))
                segs.append(_serialize_scalar(getattr(c, "subtarget", "")))
                segs.append(_serialize_scalar(getattr(c, "influence", 0.0)))
                # Hash other settings too
                segs.append(_hash_rna_properties(c))
                parts.append("|".join(segs))
            except Exception:
                pass
    except Exception:
        pass
    return _sha256(";".join(parts))


def _hash_drivers(idblock) -> str:
    parts: List[str] = []
    try:
        ad = getattr(idblock, "animation_data", None)
        if not ad:
            return ""
        for fcu in getattr(ad, "drivers", []) or []:
            try:
                drv = fcu.driver
                segs = [
                    str(getattr(fcu, "data_path", "")),
                    str(int(getattr(fcu, "array_index", 0))),
                    str(getattr(drv, "type", "")),
                    str(getattr(drv, "expression", "")),
                ]
                # Variables
                vparts: List[str] = []
                for v in getattr(drv, "variables", []) or []:
                    try:
                        tparts: List[str] = [str(getattr(v, "type", "")), str(getattr(v, "name", ""))]
                        for t in getattr(v, "targets", []) or []:
                            try:
                                tparts.extend([
                                    _hash_pointer_value(getattr(t, "id", None)),
                                    str(getattr(t, "data_path", "")),
                                    str(getattr(t, "transform_type", "")),
                                ])
                            except Exception:
                                pass
                        vparts.append("/".join(tparts))
                    except Exception:
                        pass
                segs.append("{" + ";".join(vparts) + "}")
                parts.append("|".join(segs))
            except Exception:
                pass
    except Exception:
        pass
    return _sha256("\n".join(sorted(parts)))


def _hash_node_tree(nt) -> str:
    if nt is None:
        return ""
    try:
        n_parts: List[str] = []
        for nd in getattr(nt, "nodes", []) or []:
            try:
                base = [str(getattr(nd, "bl_idname", getattr(nd, "type", ""))), nd.name or "", nd.label or ""]
                base.append(str(int(getattr(nd, "mute", False))))
                base.append(str(int(getattr(nd, "hide", False))))
                # Stable settings via RNA props
                base.append(_hash_rna_properties(nd))
                n_parts.append("|".join(base))
            except Exception:
                pass
        l_parts: List[str] = []
        for lk in getattr(nt, "links", []) or []:
            try:
                fn = getattr(getattr(lk, "from_node", None), "name", "") or ""
                fs = getattr(getattr(lk, "from_socket", None), "name", "") or ""
                tn = getattr(getattr(lk, "to_node", None), "name", "") or ""
                ts = getattr(getattr(lk, "to_socket", None), "name", "") or ""
                l_parts.append("->".join([fn, fs, tn, ts]))
            except Exception:
                pass
        return _sha256("N:" + "\n".join(sorted(n_parts)) + "\nL:" + "\n".join(sorted(l_parts)))
    except Exception:
        return ""


def _hash_material(mat) -> str:
    if not mat:
        return ""
    try:
        parts: List[str] = [mat.name or ""]
        parts.append("use_nodes:" + ("1" if getattr(mat, "use_nodes", False) else "0"))
        for a in ("blend_method", "shadow_method", "alpha_threshold", "blend_shadow", "use_backface_culling"):
            if hasattr(mat, a):
                parts.append(f"{a}:{_serialize_scalar(getattr(mat, a))}")
        nt = getattr(mat, "node_tree", None)
        parts.append("nt:" + _hash_node_tree(nt))
        return _sha256("|".join(parts))
    except Exception:
        return ""


def _hash_particles(obj) -> str:
    parts: List[str] = []
    try:
        for psys in getattr(obj, "particle_systems", []) or []:
            try:
                p = [psys.name or ""]
                st = getattr(psys, "settings", None)
                p.append(getattr(st, "name", "") if st else "")
                if st:
                    # Important flags
                    for a in ("type", "count", "frame_start", "frame_end", "lifetime", "emit_from", "render_type", "use_rotations"):
                        if hasattr(st, a):
                            p.append(f"{a}:{_serialize_scalar(getattr(st, a))}")
                    # Reference targets
                    for a in ("instance_object", "instance_collection", "material_slot"):
                        if hasattr(st, a):
                            p.append(f"{a}:{_hash_pointer_value(getattr(st, a))}")
                parts.append("|".join(p))
            except Exception:
                pass
    except Exception:
        pass
    return _sha256("\n".join(sorted(parts)))


def _hash_mesh_uv_data(me) -> str:
    try:
        uvl = getattr(me, "uv_layers", None)
        if not uvl:
            return ""
        layer_hashes: List[str] = []
        for uv in uvl:
            try:
                coords: List[str] = []
                for lu in uv.data:
                    try:
                        coords.append(f"{float(lu.uv.x):.6f},{float(lu.uv.y):.6f}")
                    except Exception:
                        coords.append("0,0")
                layer_hashes.append(_sha256("|".join(coords)))
            except Exception:
                pass
        return _list_hash(layer_hashes)
    except Exception:
        return ""


def _hash_mesh_color_attributes(me) -> str:
    # Support new color_attributes and legacy vertex_colors
    try:
        layer_hashes: List[str] = []
        cols = getattr(me, "color_attributes", None)
        if cols:
            for ca in cols:
                try:
                    vals: List[str] = []
                    data = getattr(ca, "data", None)
                    if data is None:
                        continue
                    for item in data:
                        col = getattr(item, "color", None)
                        if col is not None:
                            vals.append(_fmt_floats((col[0], col[1], col[2], col[3] if len(col) > 3 else 1.0)))
                    layer_hashes.append(_sha256("|".join(vals)))
                except Exception:
                    pass
        else:
            vcols = getattr(me, "vertex_colors", None)
            if vcols:
                for vc in vcols:
                    try:
                        vals: List[str] = []
                        for item in vc.data:
                            c = getattr(item, "color", None)
                            if c is not None:
                                vals.append(_fmt_floats((c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0)))
                        layer_hashes.append(_sha256("|".join(vals)))
                    except Exception:
                        pass
        return _list_hash(layer_hashes)
    except Exception:
        return ""


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
    # Materials meta (hash material properties and node trees)
    try:
        mats_meta: List[str] = []
        for slot in getattr(obj, "material_slots", []) or []:
            try:
                mats_meta.append(_hash_material(getattr(slot, "material", None)))
            except Exception:
                pass
        sig["materials_meta"] = _list_hash(mats_meta)
    except Exception:
        sig["materials_meta"] = ""

    # Visibility & render flags
    try:
        vparts = [
            str(int(getattr(obj, "hide_viewport", False))),
            str(int(getattr(obj, "hide_render", False))),
            str(int(getattr(obj, "hide_select", False))) if hasattr(obj, "hide_select") else "0",
            str(getattr(obj, "display_type", "")),
            str(getattr(obj, "instance_type", "")),
        ]
        # Instance targets
        for a in ("instance_collection", "instance_object"):
            try:
                vparts.append(_hash_pointer_value(getattr(obj, a, None)))
            except Exception:
                vparts.append("")
        sig["visibility_hash"] = _sha256("|".join(vparts))
    except Exception:
        sig["visibility_hash"] = ""

    # Object constraints summary
    try:
        sig["constraints_hash"] = _hash_constraints(getattr(obj, "constraints", []))
    except Exception:
        sig["constraints_hash"] = ""

    # Custom properties (ID props) on object and its data
    try:
        parts = [_hash_id_properties(obj)]
        if getattr(obj, "data", None) is not None:
            try:
                parts.append(_hash_id_properties(obj.data))
            except Exception:
                pass
        sig["idprops_hash"] = _list_hash(parts)
    except Exception:
        sig["idprops_hash"] = ""

    # Drivers on object and its data
    try:
        dparts = [_hash_drivers(obj)]
        if getattr(obj, "data", None) is not None:
            dparts.append(_hash_drivers(obj.data))
        sig["drivers_hash"] = _list_hash(dparts)
    except Exception:
        sig["drivers_hash"] = ""

    # Particle systems
    try:
        sig["particles_meta"] = _hash_particles(obj)
    except Exception:
        sig["particles_meta"] = ""

    obj_type = getattr(obj, "type", None)
    has_data = getattr(obj, "data", None) is not None

    # Modifiers (available on many object types): include both stack and settings
    try:
        mods_all = [(m.type, m.name, m) for m in getattr(obj, "modifiers", [])]
    except Exception:
        mods_all = []
    if mods_all:
        sig["modifiers"] = _list_hash([f"{t}:{n}" for t, n, _ in mods_all])
        try:
            def _serialize_val(v):
                try:
                    if isinstance(v, float):
                        return f"{v:.6f}"
                    if isinstance(v, (list, tuple)):
                        parts = []
                        for x in v:
                            if isinstance(x, float):
                                parts.append(f"{float(x):.6f}")
                            else:
                                parts.append(str(x))
                        return "(" + ",".join(parts) + ")"
                    return str(v)
                except Exception:
                    return ""

            def _modifier_settings_signature(m) -> str:
                parts: List[str] = []
                SKIP = {"name", "type", "rna_type", "bl_rna"}
                try:
                    for p in m.bl_rna.properties:  # type: ignore[attr-defined]
                        try:
                            pid = getattr(p, "identifier", "")
                        except Exception:
                            pid = ""
                        if not pid or pid in SKIP:
                            continue
                        try:
                            if getattr(p, "is_hidden", False) or getattr(p, "is_readonly", False):
                                continue
                        except Exception:
                            pass
                        try:
                            ptype = getattr(p, "type", None)
                        except Exception:
                            ptype = None
                        if ptype in {"POINTER", "COLLECTION"}:
                            if pid == "node_group":
                                try:
                                    ng = getattr(m, "node_group", None)
                                    parts.append(f"node_group:{getattr(ng, 'name', '') if ng else ''}")
                                except Exception:
                                    pass
                            continue
                        try:
                            val = getattr(m, pid)
                        except Exception:
                            continue
                        if callable(val):
                            continue
                        try:
                            if hasattr(val, "__len__") and not isinstance(val, (str, bytes)):
                                try:
                                    seq = [val[i] for i in range(len(val))]
                                except Exception:
                                    seq = None
                                if seq is not None and len(seq) <= 16:
                                    sval = _serialize_val(seq)
                                    parts.append(f"{pid}:{sval}")
                                    continue
                        except Exception:
                            pass
                        parts.append(f"{pid}:{_serialize_val(val)}")
                except Exception:
                    pass
                parts_sorted = sorted(parts)
                return _sha256("|".join(parts_sorted))

            mods_meta = [f"{t}:{n}:{_modifier_settings_signature(m)}" for t, n, m in mods_all]
            sig["modifiers_meta"] = _list_hash(mods_meta)
        except Exception:
            sig["modifiers_meta"] = ""

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
        # Vertex group names
        vgn = [vg.name for vg in getattr(obj, "vertex_groups", [])]
        sig["vgroups"] = _list_hash(sorted(vgn))
        # UV layers names (order)
        uvl = getattr(me, "uv_layers", None)
        uvs = [uv.name for uv in uvl] if uvl else []
        sig["uv_meta"] = _list_hash(uvs)
        # UV data values hash
        try:
            sig["uv_data_hash"] = _hash_mesh_uv_data(me)
        except Exception:
            sig["uv_data_hash"] = ""
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
        # Shapekey points geometry hash (expensive but deterministic)
        try:
            if kb:
                sparts: List[str] = []
                for k in kb:
                    try:
                        if (k.name or "").lower() == "basis":
                            continue
                        coords: List[str] = []
                        for d in k.data:
                            co = getattr(d, "co", None)
                            if co is not None:
                                coords.append(_fmt_floats((co.x, co.y, co.z)))
                        sparts.append(f"{k.name}:{_sha256('|'.join(coords))}")
                    except Exception:
                        pass
                sig["shapekeys_points_hash"] = _sha256("\n".join(sorted(sparts)))
            else:
                sig["shapekeys_points_hash"] = ""
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
        # Color attributes hash
        try:
            sig["color_attr_hash"] = _hash_mesh_color_attributes(me)
        except Exception:
            sig["color_attr_hash"] = ""
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
    elif obj_type == "EMPTY":
        # Empties and instancing info
        vals = []
        try:
            vals.append(str(getattr(obj, "empty_display_type", getattr(obj, "display_type", ""))))
            vals.append(f"{float(getattr(obj, 'empty_display_size', getattr(obj, 'empty_display_size', 1.0))):.6f}")
            vals.append(str(getattr(obj, "instance_type", "")))
            vals.append(_hash_pointer_value(getattr(obj, "instance_collection", None)))
            vals.append(_hash_pointer_value(getattr(obj, "instance_object", None)))
            vals.append(str(int(getattr(obj, "use_instance_faces", False))))
        except Exception:
            pass
        sig["empty_meta"] = _sha256("|".join(vals))
    elif obj_type == "LATTICE" and has_data:
        try:
            sig["lattice_meta"] = _hash_rna_properties(obj.data)
        except Exception:
            sig["lattice_meta"] = ""
    elif obj_type == "SURFACE" and has_data:
        try:
            sig["surface_meta"] = _hash_rna_properties(obj.data)
        except Exception:
            sig["surface_meta"] = ""
    elif obj_type == "META" and has_data:
        try:
            sig["metaball_meta"] = _hash_rna_properties(obj.data)
        except Exception:
            sig["metaball_meta"] = ""
    elif obj_type == "FONT" and has_data:
        try:
            vals = [getattr(obj.data, "body", "")]
            vals.append(_hash_rna_properties(obj.data))
            sig["font_meta"] = _sha256("|".join(vals))
        except Exception:
            sig["font_meta"] = ""
    elif obj_type == "POINTCLOUD" and has_data:
        try:
            sig["pointcloud_meta"] = _hash_rna_properties(obj.data)
        except Exception:
            sig["pointcloud_meta"] = ""
    elif obj_type == "VOLUME" and has_data:
        try:
            sig["volume_meta"] = _hash_rna_properties(obj.data)
        except Exception:
            sig["volume_meta"] = ""
    elif obj_type in {"GPENCIL", "GREASEPENCIL"} and has_data:
        try:
            sig["grease_pencil_meta"] = _hash_rna_properties(obj.data)
        except Exception:
            sig["grease_pencil_meta"] = ""

    # Geometry Nodes internals (node groups used by NODES modifiers)
    try:
        gn_hashes: List[str] = []
        for m in getattr(obj, "modifiers", []) or []:
            try:
                if getattr(m, "type", "") == "NODES":
                    ng = getattr(m, "node_group", None)
                    nt = getattr(ng, "node_tree", getattr(m, "node_group", None))
                    gn_hashes.append(_hash_node_tree(nt))
            except Exception:
                pass
        sig["geom_nodes_hash"] = _list_hash(gn_hashes)
    except Exception:
        sig["geom_nodes_hash"] = ""
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
            s.get("shapekeys_meta", ""),
            s.get("shapekeys_values", ""),
            s.get("shapekeys_points_hash", ""),
            s.get("materials", ""),
            s.get("materials_meta", ""),
            s.get("constraints_hash", ""),
            s.get("idprops_hash", ""),
            s.get("visibility_hash", ""),
            s.get("drivers_hash", ""),
            s.get("particles_meta", ""),
            s.get("geom_nodes_hash", ""),
            str(s.get("edges", 0)),
            str(s.get("polygons", 0)),
            s.get("geo_hash", ""),
            s.get("color_attr_hash", ""),
            s.get("light_meta", ""),
            s.get("camera_meta", ""),
            s.get("collection_path", ""),
            s.get("curve_meta", ""),
            s.get("curve_points_hash", ""),
            s.get("armature_meta", ""),
            s.get("armature_bones_hash", ""),
            s.get("pose_bones_hash", ""),
            s.get("empty_meta", ""),
            s.get("lattice_meta", ""),
            s.get("surface_meta", ""),
            s.get("metaball_meta", ""),
            s.get("font_meta", ""),
            s.get("pointcloud_meta", ""),
            s.get("volume_meta", ""),
            s.get("grease_pencil_meta", ""),
        ]))
    collection_hash = _sha256("\n".join(parts))
    return obj_sigs, collection_hash


def load_index() -> Dict:
    """Load the Git Blend index from JSON. If missing or invalid, return an empty structure."""
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
        "modifiers", "modifiers_meta", "vgroups", "uv_meta", "uv_data_hash",
        "shapekeys_meta", "shapekeys_values", "shapekeys_points_hash",
        "materials", "materials_meta",
        "constraints_hash", "idprops_hash", "visibility_hash", "drivers_hash",
        "particles_meta", "geom_nodes_hash",
        "geo_hash", "color_attr_hash",
    "light_meta", "camera_meta",
    "curve_meta", "curve_points_hash",
    "armature_meta", "armature_bones_hash", "pose_bones_hash",
    "empty_meta", "lattice_meta", "surface_meta", "metaball_meta", "font_meta", "pointcloud_meta", "volume_meta", "grease_pencil_meta",
    )
    for nm in intersect:
        a = curr_objs.get(nm, {})
        b = prev_objs.get(nm, {})
        # Compare base keys always
        for k in base_keys:
            # Backward compatible: treat missing as empty string
            if str(a.get(k, "")) != str(b.get(k, "")):
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
