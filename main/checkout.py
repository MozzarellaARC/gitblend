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

    # Backup disabled per user request (was previously created in .gitblend/backups)

    # Open snapshot
    try:
        bpy.ops.wm.open_mainfile(filepath=str(snapshot_path), load_ui=False)
    except Exception as e:
        _report('ERROR', f'Failed to open snapshot: {e}')
        return False

    # Save back to original path
    try:
        bpy.ops.wm.save_as_mainfile(filepath=str(current_file), copy=False)
    except Exception as e:
        _report('WARNING', f'Loaded snapshot but failed to re-save to original path: {e}')

    # Rebuild commit UI list & restore selection
    try:
        wm = bpy.context.window_manager  # type: ignore
        wm['gitblend_loading_history'] = True
        populate_ui_from_metadata(bpy.context)
    finally:
        try:
            if 'gitblend_loading_history' in bpy.context.window_manager:  # type: ignore
                del bpy.context.window_manager['gitblend_loading_history']  # type: ignore
        except Exception:
            pass
    try:
        props_after = getattr(bpy.context.scene, 'gitblend_props', None)
        if props_after:
            for i, c in enumerate(props_after.commits):
                if c.hash == target_hash:
                    props_after.commits_index = i
                    break
    except Exception:
        pass
    _report('INFO', f'Checked out commit {target_hash[:8]} -> {snapshot_name} (path preserved, no backup)')
    return True


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