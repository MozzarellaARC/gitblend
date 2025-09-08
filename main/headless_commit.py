import bpy  # type: ignore
import sys
import argparse
import os
import json


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

    # Determine object set to import using previous baseline if available
    if args.previous and os.path.exists(args.previous):
        prev_names = list_objects_in_blend(args.previous)
    else:
        prev_names = set()

    requested = set(args.object or [])
    added_or_changed = sorted(list(requested - prev_names)) if prev_names else sorted(list(requested))
    removed = sorted(list(prev_names - requested)) if prev_names else []

    imported = append_objects(args.source, added_or_changed)
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
                "requested": sorted(list(requested)),
                "imported": imported,
                "removed_vs_base": removed,
            }
            with open(args.manifest, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            print(f"[git_blend] WARN: Failed to write manifest: {e}")

    print(f"[git_blend] OK: saved {args.output} with objects: {', '.join(imported)}")


if __name__ == "__main__":
    main()
