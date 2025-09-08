import bpy  # type: ignore
import hashlib


def _fmt_f(v: float) -> bytes:
    try:
        return f"{float(v):.6f}".encode()
    except Exception:
        return b"0.000000"


def _update_vec3(h, v):
    try:
        h.update(_fmt_f(v.x))
        h.update(_fmt_f(v.y))
        h.update(_fmt_f(v.z))
    except Exception:
        pass


def list_objects_in_blend(blend_path: str) -> set[str]:
    names: set[str] = set()
    try:
        with bpy.data.libraries.load(blend_path, link=True) as (data_from, _data_to):
            names.update(data_from.objects)
    except Exception as e:
        print(f"[git_blend] WARN: failed to list objects from {blend_path}: {e}")
    return names


def load_object_once(blend_path: str, name: str):
    obj = None
    try:
        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            if name in data_from.objects:
                data_to.objects = [name]
            else:
                return None
        for o in data_to.objects:
            if o is not None:
                obj = o
                break
    except Exception as e:
        print(f"[git_blend] WARN: failed to load object {name} from {blend_path}: {e}")
    return obj


def hash_mesh(me):
    h = hashlib.sha256()
    try:
        h.update(str(len(me.vertices)).encode())
        for v in me.vertices:
            _update_vec3(h, v.co)
        h.update(str(len(me.edges)).encode())
        h.update(str(len(me.polygons)).encode())
    except Exception:
        pass
    return h.hexdigest()


def hash_curve(cv) -> str:
    h = hashlib.sha256()
    try:
        h.update(str(len(cv.splines)).encode())
        for sp in cv.splines:
            try:
                h.update((sp.type or "").encode())
                # generic spline props
                for attr in ("use_cyclic_u", "use_cyclic_v", "resolution_u", "resolution_v", "order_u", "order_v"):
                    try:
                        h.update(str(getattr(sp, attr)).encode())
                    except Exception:
                        pass
                if sp.type == 'BEZIER':
                    for bp in sp.bezier_points:
                        _update_vec3(h, bp.co)
                        _update_vec3(h, bp.handle_left)
                        _update_vec3(h, bp.handle_right)
                        try:
                            h.update(_fmt_f(bp.tilt))
                            h.update(_fmt_f(bp.radius))
                        except Exception:
                            pass
                else:
                    for p in sp.points:
                        _update_vec3(h, p.co)
                        try:
                            h.update(_fmt_f(getattr(p, 'tilt', 0.0)))
                            h.update(_fmt_f(getattr(p, 'radius', 0.0)))
                            h.update(_fmt_f(getattr(p, 'weight', 0.0)))
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass
    return h.hexdigest()


def hash_camera(cam) -> str:
    h = hashlib.sha256()
    try:
        h.update((cam.type or "").encode())
        for attr in ("lens", "sensor_width", "sensor_height", "shift_x", "shift_y", "clip_start", "clip_end", "ortho_scale"):
            try:
                h.update(_fmt_f(getattr(cam, attr)))
            except Exception:
                pass
    except Exception:
        pass
    return h.hexdigest()


def hash_light(lgt) -> str:
    h = hashlib.sha256()
    try:
        h.update((lgt.type or "").encode())
        try:
            c = getattr(lgt, 'color', None)
            if c is not None:
                for v in c[:3]:
                    h.update(_fmt_f(v))
        except Exception:
            pass
        for attr in ("energy", "shadow_soft_size", "spot_size", "spot_blend", "shape", "size", "size_y"):
            try:
                v = getattr(lgt, attr)
                if isinstance(v, (int, float)):
                    h.update(_fmt_f(v))
                else:
                    h.update(str(v).encode())
            except Exception:
                pass
    except Exception:
        pass
    return h.hexdigest()


def hash_armature(arm) -> str:
    h = hashlib.sha256()
    try:
        names = sorted([b.name for b in arm.bones])
        h.update(str(len(names)).encode())
        for name in names:
            try:
                b = arm.bones.get(name)
                if b is None:
                    continue
                h.update(name.encode())
                h.update(((b.parent.name) if b.parent else "").encode())
                _update_vec3(h, b.head_local)
                _update_vec3(h, b.tail_local)
                try:
                    h.update(_fmt_f(b.roll))
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        pass
    return h.hexdigest()


def hash_empty(o) -> str:
    h = hashlib.sha256()
    try:
        for attr in ("empty_display_type", "empty_display_size"):
            try:
                v = getattr(o, attr)
                if isinstance(v, (int, float)):
                    h.update(_fmt_f(v))
                else:
                    h.update(str(v).encode())
            except Exception:
                pass
    except Exception:
        pass
    return h.hexdigest()


def hash_object(o) -> str:
    h = hashlib.sha256()
    try:
        h.update((o.type or "").encode())
        if hasattr(o, "location"):
            _update_vec3(h, o.location)
        if hasattr(o, "scale"):
            _update_vec3(h, o.scale)
        if hasattr(o, "rotation_euler") and o.rotation_mode in {"XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"}:
            e = o.rotation_euler
            h.update(b"E:")
            _update_vec3(h, e)
        elif hasattr(o, "rotation_quaternion"):
            q = o.rotation_quaternion
            h.update(b"Q:")
            try:
                h.update(_fmt_f(q.w))
                h.update(_fmt_f(q.x))
                h.update(_fmt_f(q.y))
                h.update(_fmt_f(q.z))
            except Exception:
                pass
        # Type-specific data hashing
        if getattr(o, 'data', None) is not None:
            try:
                if o.type == 'MESH' and getattr(o, 'data', None) is not None:
                    h.update(hash_mesh(o.data).encode())
                elif o.type == 'CURVE':
                    h.update(hash_curve(o.data).encode())
                elif o.type == 'CAMERA':
                    h.update(hash_camera(o.data).encode())
                elif o.type == 'LIGHT':
                    h.update(hash_light(o.data).encode())
                elif o.type == 'ARMATURE':
                    h.update(hash_armature(o.data).encode())
                elif o.type == 'EMPTY':
                    h.update(hash_empty(o).encode())
            except Exception:
                pass
        try:
            mats = []
            if hasattr(o, 'material_slots') and o.material_slots:
                for slot in o.material_slots:
                    if slot and slot.material:
                        mats.append(slot.material.name)
            elif getattr(o.data, 'materials', None):
                for m in o.data.materials:
                    if m:
                        mats.append(m.name)
            for m in mats:
                h.update(m.encode())
        except Exception:
            pass
        try:
            if hasattr(o, 'modifiers'):
                for m in o.modifiers:
                    h.update((m.type + ":" + m.name).encode())
        except Exception:
            pass
    except Exception:
        pass
    return h.hexdigest()


def compute_hashes_for_blend(blend_path: str, object_names: list[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name in object_names:
        o = load_object_once(blend_path, name)
        if o is None:
            continue
        try:
            hashes[name] = hash_object(o)
        finally:
            try:
                if getattr(o, 'data', None) is not None and hasattr(o.data, 'users') and o.data.users == 1:
                    data_block = o.data
                else:
                    data_block = None
                bpy.data.objects.remove(o, do_unlink=True)
                if data_block is not None and getattr(data_block, 'users', 0) == 0:
                    try:
                        t = data_block.__class__.__name__
                        if t == 'Mesh' and hasattr(bpy.data, 'meshes'):
                            bpy.data.meshes.remove(data_block)
                        elif t == 'Curve' and hasattr(bpy.data, 'curves'):
                            bpy.data.curves.remove(data_block)
                        elif t == 'Camera' and hasattr(bpy.data, 'cameras'):
                            bpy.data.cameras.remove(data_block)
                        elif t == 'Light' and hasattr(bpy.data, 'lights'):
                            bpy.data.lights.remove(data_block)
                        elif t == 'Armature' and hasattr(bpy.data, 'armatures'):
                            bpy.data.armatures.remove(data_block)
                        elif t == 'Lattice' and hasattr(bpy.data, 'lattices'):
                            bpy.data.lattices.remove(data_block)
                        elif t == 'GreasePencil' and hasattr(bpy.data, 'grease_pencils'):
                            bpy.data.grease_pencils.remove(data_block)
                    except Exception:
                        pass
            except Exception:
                pass
    return hashes
