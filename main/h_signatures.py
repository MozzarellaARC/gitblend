import bpy  # type: ignore
import hashlib


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
            h.update((f"{v.co.x:.6f},{v.co.y:.6f},{v.co.z:.6f}").encode())
        h.update(str(len(me.edges)).encode())
        h.update(str(len(me.polygons)).encode())
    except Exception:
        pass
    return h.hexdigest()


def hash_object(o) -> str:
    h = hashlib.sha256()
    try:
        h.update((o.type or "").encode())
        if hasattr(o, "location"):
            h.update((f"{o.location.x:.6f},{o.location.y:.6f},{o.location.z:.6f}").encode())
        if hasattr(o, "scale"):
            h.update((f"{o.scale.x:.6f},{o.scale.y:.6f},{o.scale.z:.6f}").encode())
        if hasattr(o, "rotation_euler") and o.rotation_mode in {"XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"}:
            e = o.rotation_euler
            h.update((f"E:{e.x:.6f},{e.y:.6f},{e.z:.6f}").encode())
        elif hasattr(o, "rotation_quaternion"):
            q = o.rotation_quaternion
            h.update((f"Q:{q.w:.6f},{q.x:.6f},{q.y:.6f},{q.z:.6f}").encode())
        if o.type == 'MESH' and getattr(o, 'data', None) is not None:
            h.update(hash_mesh(o.data).encode())
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
                if data_block is not None:
                    if hasattr(bpy.data, 'meshes') and data_block.__class__.__name__ == 'Mesh' and data_block.users == 0:
                        bpy.data.meshes.remove(data_block)
            except Exception:
                pass
    return hashes
