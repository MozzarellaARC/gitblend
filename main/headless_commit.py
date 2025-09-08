import bpy  # type: ignore
import sys
import argparse
import os
import json
import hashlib


def parse_args(argv):
    # Blender passes args to python after a standalone "--"
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Git Blend headless commit")
    parser.add_argument("--source", required=True, help="Path to source .blend for appending")
    parser.add_argument("--output", required=True, help="Path to write the new .blend file (diff blend)")
    parser.add_argument("--object", action="append", default=[], help="Object name to append (repeatable)")
    parser.add_argument("--previous", required=False, help="Path to previous baseline .blend for diff")
    parser.add_argument("--manifest", required=False, help="Path to write diff manifest JSON")
    return parser.parse_args(argv)


def get_utils_template_path() -> str:
    # This script is located in .../git_blend/main/headless_commit.py
    # utils dir lives at .../git_blend/utils/template.blend
    addon_root = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(addon_root, 'utils', 'template.blend')


def append_objects(source_blend: str, object_names: list[str]):
    library_path = source_blend + "\\Object"
    imported = []
    for name in object_names:
        with bpy.data.libraries.load(source_blend, link=False) as (data_from, data_to):
            # Only append the requested object if present
            if name in data_from.objects:
                data_to.objects = [name]
            else:
                print(f"[git_blend] WARN: object '{name}' not found in source")
                continue
        for obj in data_to.objects:
            if obj is not None:
                bpy.context.scene.collection.objects.link(obj)
                imported.append(obj.name)
    return imported


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
        # transforms
        if hasattr(o, "location"):
            h.update((f"{o.location.x:.6f},{o.location.y:.6f},{o.location.z:.6f}").encode())
        if hasattr(o, "scale"):
            h.update((f"{o.scale.x:.6f},{o.scale.y:.6f},{o.scale.z:.6f}").encode())
        # rotation (try euler then quaternion)
        if hasattr(o, "rotation_euler") and o.rotation_mode in {"XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"}:
            e = o.rotation_euler
            h.update((f"E:{e.x:.6f},{e.y:.6f},{e.z:.6f}").encode())
        elif hasattr(o, "rotation_quaternion"):
            q = o.rotation_quaternion
            h.update((f"Q:{q.w:.6f},{q.x:.6f},{q.y:.6f},{q.z:.6f}").encode())
        # mesh data
        if o.type == 'MESH' and getattr(o, 'data', None) is not None:
            h.update(hash_mesh(o.data).encode())
        # materials
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
        # modifiers (names and types)
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
            # cleanup temp object and data
            try:
                if getattr(o, 'data', None) is not None and hasattr(o.data, 'users') and o.data.users == 1:
                    data_block = o.data
                else:
                    data_block = None
                bpy.data.objects.remove(o, do_unlink=True)
                if data_block is not None:
                    # Remove mesh if it has no users
                    if hasattr(bpy.data, 'meshes') and data_block.__class__.__name__ == 'Mesh' and data_block.users == 0:
                        bpy.data.meshes.remove(data_block)
            except Exception:
                pass
    return hashes


def main():
    args = parse_args(sys.argv)

    # Open the template .blend from utils as the base file
    template_path = get_utils_template_path()
    if not os.path.exists(template_path):
        print(f"[git_blend] ERROR: Template not found: {template_path}")
        sys.exit(1)

    res = bpy.ops.wm.open_mainfile(filepath=template_path)
    if res != {'FINISHED'}:
        print(f"[git_blend] ERROR: Failed to open template: {template_path}")
        sys.exit(1)

    # Determine object sets via content hashing
    # If no explicit object list provided, use all objects from source
    if args.object:
        current_names = sorted(set(args.object))
    else:
        current_names = sorted(list(list_objects_in_blend(args.source)))

    prev_names_set: set[str] = set()
    prev_hashes: dict[str, str] = {}
    prev_manifest_path = None
    if args.previous and os.path.exists(args.previous):
        # Attempt to find sibling manifest next to previous .blend
        base, _ = os.path.splitext(args.previous)
        candidate = base + ".json"
        if os.path.exists(candidate):
            prev_manifest_path = candidate
        # Load prev hashes from manifest if available, else compute from .blend
        if prev_manifest_path:
            try:
                with open(prev_manifest_path, 'r', encoding='utf-8') as f:
                    pm = json.load(f)
                    if isinstance(pm, dict) and 'hashes' in pm:
                        prev_hashes = {k: str(v) for k, v in pm['hashes'].items()}
                        prev_names_set = set(prev_hashes.keys())
            except Exception as e:
                print(f"[git_blend] WARN: failed to read previous manifest: {e}")
        if not prev_hashes:
            # Compute hashes directly from previous .blend (full scan)
            prev_names_set = set(list_objects_in_blend(args.previous))
            prev_hashes = compute_hashes_for_blend(args.previous, sorted(list(prev_names_set)))

    # Compute current hashes from source .blend
    current_hashes = compute_hashes_for_blend(args.source, current_names)

    curr_set = set(current_names)
    added = sorted(list(curr_set - prev_names_set)) if prev_names_set else current_names
    removed = sorted(list(prev_names_set - curr_set)) if prev_names_set else []
    changed = []
    if prev_hashes:
        for name in (curr_set & prev_names_set):
            if current_hashes.get(name) != prev_hashes.get(name):
                changed.append(name)
    changed = sorted(changed)

    to_import = sorted(list(set(added) | set(changed)))
    imported = append_objects(args.source, to_import)
    if not imported:
        print("[git_blend] ERROR: No objects imported; aborting save.")
        sys.exit(2)

    result = bpy.ops.wm.save_as_mainfile(filepath=args.output, copy=False)
    if result != {'FINISHED'}:
        print("[git_blend] ERROR: Failed to save output blend")
        sys.exit(3)

    # Write manifest if requested
    if args.manifest:
        try:
            manifest = {
                "base": args.previous or None,
                "output": args.output,
                "template": template_path,
                "requested": current_names,
                "imported": imported,
                "removed_vs_base": removed,
                "added": added,
                "changed": changed,
                "hashes": current_hashes,  # full-scene hashes for accurate next diff
            }
            with open(args.manifest, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            print(f"[git_blend] WARN: Failed to write manifest: {e}")

    print(f"[git_blend] OK: saved {args.output} with objects: {', '.join(imported)}")


if __name__ == "__main__":
    main()
