import bpy  # type: ignore
from pathlib import Path
from .initialize import (
    is_gitblend_initialized,
    is_ui_synced_with_metadata,
    load_metadata,
    get_gitblend_dir,
    populate_ui_from_metadata,
)
import time
from typing import Optional


def _perform_checkout(context, target_index: int, report_fn=None) -> bool:
    """Core checkout implementation shared by operator and auto-select callback.

    Returns True on success, False on failure. report_fn(level, msg) is optional.
    """
    def _report(level, msg):
        if report_fn:
            report_fn(level, msg)
        else:
            print(f"[gitblend][{level}] {msg}")

    blend_path = bpy.data.filepath
    if not blend_path:
        _report('ERROR', 'Please save the .blend file first.')
        return False
    current_file = Path(blend_path).resolve()
    project_dir = current_file.parent

    if not is_gitblend_initialized(project_dir):
        _report('ERROR', 'Repository not initialized.')
        return False
    # We allow auto-checkout even if UI not synced (e.g., indexes just changed) but warn.
    if not is_ui_synced_with_metadata(context):
        _report('INFO', 'Proceeding while UI not fully synced.')

    props = getattr(context.scene, 'gitblend_props', None)
    if not props or target_index < 0 or target_index >= len(props.commits):
        _report('ERROR', 'Invalid commit selection.')
        return False

    selected = props.commits[target_index]
    target_hash = selected.hash
    metadata = load_metadata(project_dir)
    commit_entry: Optional[dict] = None
    for c in metadata.get('commits', []):
        if c.get('hash') == target_hash:
            commit_entry = c
            break
    if not commit_entry:
        _report('ERROR', f'Commit metadata for hash {target_hash[:8]} not found.')
        return False

    snapshot_name = commit_entry.get('snapshot') or f"{target_hash}.blend"
    snapshot_path = get_gitblend_dir(project_dir) / snapshot_name
    if not snapshot_path.exists():
        _report('ERROR', f'Snapshot file missing: {snapshot_name}')
        return False

    # Scene-based restore (no opening mainfile): purge selected data blocks and append from snapshot.
    try:
        _purge_and_restore_from_snapshot(snapshot_path, _report)
    except Exception as e:
        _report('ERROR', f'Scene-based restore failed: {e}')
        return False

    _report('INFO', f'Checked out commit {target_hash[:8]} -> {snapshot_name} (scene-based, no backup)')
    return True


def _purge_and_restore_from_snapshot(snapshot_path: Path, report):
    """Remove specified datablocks then append all scenes + their linked data from snapshot.

    Purge order chosen to reduce dependency issues. Blender automatically clears orphaned
    datablocks when running outliner cleanups, but we manually remove to avoid duplication.
    """
    # Datablock categories to fully purge (objects first so they release users of meshes/materials)
    purge_order = [
        ('objects', bpy.data.objects),
        ('meshes', bpy.data.meshes),
        ('materials', bpy.data.materials),
        ('images', bpy.data.images),
        ('texts', bpy.data.texts),
        ('actions', bpy.data.actions),
    ]

    # Deselect & ensure not in edit/pose mode
    try:
        if bpy.ops.object.mode_set.poll():  # type: ignore
            bpy.ops.object.mode_set(mode='OBJECT')  # type: ignore
    except Exception:
        pass

    # Remove objects via unlink from scenes then remove datablock
    for label, collection in purge_order:
        try:
            items = list(collection)
            for datablock in items:
                try:
                    if label == 'objects':
                        # Unlink from all scenes/collections first
                        for scene in list(bpy.data.scenes):
                            if datablock.name in scene.objects:
                                scene.objects.unlink(datablock)
                        for coll in list(bpy.data.collections):
                            if datablock.name in coll.objects:
                                coll.objects.unlink(datablock)
                    collection.remove(datablock)
                except Exception:
                    pass
            report('INFO', f'Purged {label}: {len(items)}')
        except Exception as e:
            report('WARNING', f'Failed purging {label}: {e}')

    # Also clear scenes (after objects purged)
    for sc in list(bpy.data.scenes):
        try:
            bpy.data.scenes.remove(sc)
        except Exception:
            pass

    # Append scenes from snapshot .blend
    if not snapshot_path.exists():
        raise FileNotFoundError(snapshot_path)

    # Use library load to bring in scenes; Blender will automatically bring required linked data.
    try:
        with bpy.data.libraries.load(str(snapshot_path), link=False) as (data_from, data_to):  # type: ignore
            data_to.scenes = list(data_from.scenes)
    except Exception as e:
        raise RuntimeError(f'Failed to load scenes: {e}')

    # Set active scene to last (arbitrary) if any
    if bpy.data.scenes:
        bpy.context.window.scene = bpy.data.scenes[-1]  # type: ignore

    # Tag UI commit list for redraw (we did not reload file so properties remain); no repopulation needed.
    for window in bpy.context.window_manager.windows:  # type: ignore
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


class GITBLEND_OT_checkout(bpy.types.Operator):
    bl_idname = "gitblend.checkout"
    bl_label = "Checkout Commit"
    bl_description = "Restore the scene to the selected commit snapshot (creates a backup of current file)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):  # type: ignore
        # Minimal gating so manual invocation works; auto-checkout uses internal helper.
        # We intentionally DO NOT require UI sync here to avoid poll failures during transitions.
        blend_path = bpy.data.filepath
        if not blend_path:
            return False
        try:
            project_dir = Path(blend_path).resolve().parent
            if not is_gitblend_initialized(project_dir):
                return False
        except Exception:
            return False
        props = getattr(context.scene, "gitblend_props", None)
        if not props or props.commits_index < 0 or props.commits_index >= len(props.commits):
            return False
        return True

    def execute(self, context):  # type: ignore
        props = getattr(context.scene, 'gitblend_props', None)
        idx = props.commits_index if props else -1
        ok = _perform_checkout(context, idx, report_fn=lambda lvl, msg: self.report({lvl}, msg))
        return {'FINISHED'} if ok else {'CANCELLED'}

__all__ = ["GITBLEND_OT_checkout"]