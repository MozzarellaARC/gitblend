import bpy  # type: ignore
import sys
import argparse
import os

# Ensure relative imports work when Blender executes this file directly
_this_dir = os.path.dirname(__file__)
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

try:
    from .h_diffing import decide_changes, append_objects, write_manifest
    from .h_signatures import list_objects_in_blend
except Exception:
    # Fallback to local imports if package-relative fails
    from main.h_diffing import decide_changes, append_objects, write_manifest
    from main.h_signatures import list_objects_in_blend


def parse_args(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Git Blend headless commit (diff)")
    parser.add_argument("--source", required=True, help="Path to source .blend for appending")
    parser.add_argument("--output", required=True, help="Path to write the new .blend file (diff blend)")
    parser.add_argument("--object", action="append", default=[], help="Object name to append (repeatable)")
    parser.add_argument("--previous", required=False, help="Path to previous baseline .blend for diff")
    parser.add_argument("--manifest", required=False, help="Path to write diff manifest JSON")
    return parser.parse_args(argv)


def get_utils_template_path() -> str:
    addon_root = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(addon_root, 'utils', 'template.blend')


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

    # Determine object sets via content hashing (delegated)
    current_names, current_hashes, added, removed, changed, to_import = decide_changes(
        args.source,
        args.previous if (args.previous and os.path.exists(args.previous)) else None,
        args.object or None,
    )

    imported = append_objects(args.source, to_import)
    if not imported and not added and not changed:
        print("[git_blend] ERROR: No objects imported; aborting save.")
        sys.exit(2)

    result = bpy.ops.wm.save_as_mainfile(filepath=args.output, copy=False)
    if result != {'FINISHED'}:
        print("[git_blend] ERROR: Failed to save output blend")
        sys.exit(3)

    # Write manifest if requested
    if args.manifest:
        try:
            write_manifest(
                args.manifest,
                args.previous or None,
                args.output,
                template_path,
                current_names,
                imported,
                removed,
                added,
                changed,
                current_hashes,
            )
        except Exception as e:
            print(f"[git_blend] WARN: Failed to write manifest: {e}")

    print(f"[git_blend] OK: saved {args.output} with objects: {', '.join(imported)}")


if __name__ == "__main__":
    main()
