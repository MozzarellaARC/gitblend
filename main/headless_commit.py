import bpy  # type: ignore
import sys
import argparse


def parse_args(argv):
    # Blender passes args to python after a standalone "--"
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Git Blend headless commit")
    parser.add_argument("--source", required=True, help="Path to source .blend for appending")
    parser.add_argument("--output", required=True, help="Path to write the new .blend file")
    parser.add_argument("--object", action="append", default=[], help="Object name to append (repeatable)")
    return parser.parse_args(argv)


def ensure_empty_scene():
    # Create a new empty scene to avoid startup primitives
    # Using factory-startup should already be empty, but be defensive.
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


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


def main():
    args = parse_args(sys.argv)
    ensure_empty_scene()

    imported = append_objects(args.source, args.object)
    if not imported:
        print("[git_blend] ERROR: No objects imported; aborting save.")
        sys.exit(2)

    result = bpy.ops.wm.save_as_mainfile(filepath=args.output, copy=False)
    if result != {'FINISHED'}:
        print("[git_blend] ERROR: Failed to save output blend")
        sys.exit(3)

    print(f"[git_blend] OK: saved {args.output} with objects: {', '.join(imported)}")


if __name__ == "__main__":
    main()
