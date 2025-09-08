import bpy  # type: ignore
import json
import os
from .h_signatures import list_objects_in_blend, compute_hashes_for_blend


def _load_prev_hashes_from_manifest(previous_blend: str) -> dict[str, str] | None:
    try:
        base, _ = os.path.splitext(previous_blend)
        manifest_path = base + ".json"
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            hashes = data.get('hashes')
            if isinstance(hashes, dict):
                # coerce keys/values to str
                return {str(k): str(v) for k, v in hashes.items()}
    except Exception as e:
        print(f"[git_blend] WARN: failed reading previous manifest: {e}")
    return None


def decide_changes(source_blend: str, previous_blend: str | None, explicit_objects: list[str] | None):
    if explicit_objects:
        current_names = sorted(set(explicit_objects))
    else:
        current_names = sorted(list(list_objects_in_blend(source_blend)))

    prev_names_set = set()
    prev_hashes: dict[str, str] = {}
    if previous_blend:
        # Prefer manifest hashes for full-scene awareness when baseline is a diff
        manifest_hashes = _load_prev_hashes_from_manifest(previous_blend)
        if manifest_hashes:
            prev_hashes = manifest_hashes
            prev_names_set = set(prev_hashes.keys())
        else:
            prev_names_set = set(list_objects_in_blend(previous_blend))
            prev_hashes = compute_hashes_for_blend(previous_blend, sorted(list(prev_names_set)))

    current_hashes = compute_hashes_for_blend(source_blend, current_names)

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
    return current_names, current_hashes, added, removed, changed, to_import


def append_objects(source_blend: str, object_names: list[str]):
    imported = []
    for name in object_names:
        with bpy.data.libraries.load(source_blend, link=False) as (data_from, data_to):
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


def write_manifest(path: str, base: str | None, output: str, template: str,
                   requested: list[str], imported: list[str], removed: list[str],
                   added: list[str], changed: list[str], hashes: dict[str, str]):
    data = {
        "base": base,
        "output": output,
        "template": template,
        "requested": requested,
        "imported": imported,
        "removed_vs_base": removed,
        "added": added,
        "changed": changed,
        "hashes": hashes,
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
