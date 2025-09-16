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

    # Check if another checkout is already in progress
    wm = context.window_manager
    if wm.get('gitblend_checkout_in_progress'):
        _report('WARNING', 'Checkout already in progress, please wait.')
        return False
    
    # Set checkout lock
    wm['gitblend_checkout_in_progress'] = True
    
    try:
        blend_path = bpy.data.filepath
        if not blend_path:
            _report('ERROR', 'Please save the .blend file first.')
            return False
        current_file = Path(blend_path).resolve()
        project_dir = current_file.parent

        if not is_gitblend_initialized(project_dir):
            _report('ERROR', 'Repository not initialized.')
            return False

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

        # Scene-based recovery: Create new scene and append from commit file
        try:
            # Store the current scene name for reference
            original_scene_name = context.scene.name
            
            # Ensure we have a valid context scene
            if not context.scene:
                _report('ERROR', 'No valid scene in context')
                return False
            
            # Create a new temporary scene
            bpy.ops.scene.new(type='NEW')
            new_scene = context.scene
            new_scene_name = new_scene.name
            
            # Validate the new scene was created
            if not new_scene or new_scene_name == original_scene_name:
                _report('ERROR', 'Failed to create new temporary scene')
                return False
            
            # Find and remove the original scene
            original_scene = bpy.data.scenes.get(original_scene_name)
            if original_scene and len(bpy.data.scenes) > 1:  # Don't remove if it's the only scene
                bpy.data.scenes.remove(original_scene, do_unlink=True)
            
            # Purge orphaned data
            bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
            
            # Append scene from the commit file
            with bpy.data.libraries.load(str(snapshot_path)) as (data_from, data_to):
                # Get all scene names from the commit file
                commit_scenes = data_from.scenes
                if not commit_scenes:
                    _report('ERROR', f'No scenes found in commit file: {snapshot_name}')
                    return False
                
                # Append the first scene (or find the main scene)
                # TODO: In the future, we might want to store which scene was committed
                target_scene_name = commit_scenes[0]
                data_to.scenes = [target_scene_name]
            
            # Find the appended scene and set it as active
            appended_scene = None
            # Look for a scene that wasn't the temporary new scene
            for scene in bpy.data.scenes:
                if scene.name != new_scene_name:  # This should be the appended scene
                    appended_scene = scene
                    break
            
            if appended_scene:
                # Validate the appended scene before proceeding
                if not hasattr(appended_scene, 'name'):
                    _report('ERROR', 'Appended scene is invalid')
                    return False
                
                # Remove the temporary new scene safely
                if new_scene and new_scene.name in bpy.data.scenes:
                    bpy.data.scenes.remove(new_scene, do_unlink=True)
                
                # Set the appended scene as active with validation
                try:
                    context.window.scene = appended_scene
                except Exception as e:
                    _report('ERROR', f'Failed to set active scene: {e}')
                    return False
                
                # Rename the appended scene to maintain consistency
                # Generate a clean name based on the original scene name
                desired_name = original_scene_name
                if appended_scene.name != desired_name:
                    # Check if the desired name is available
                    if desired_name not in bpy.data.scenes:
                        try:
                            appended_scene.name = desired_name
                        except Exception:
                            # If renaming fails, keep the original name
                            pass
                    else:
                        # If there's a conflict, try to find a unique name
                        base_name = desired_name
                        counter = 1
                        while f"{base_name}.{counter:03d}" in bpy.data.scenes:
                            counter += 1
                        try:
                            appended_scene.name = f"{base_name}.{counter:03d}"
                        except Exception:
                            # If renaming fails, keep the original name
                            pass
            else:
                _report('ERROR', 'Failed to find appended scene from commit file')
                return False
                
            # Save the current state
            try:
                bpy.ops.wm.save_as_mainfile(filepath=str(current_file), copy=False)
            except Exception as e:
                _report('WARNING', f'Scene restored but failed to save to original path: {e}')
            
        except Exception as e:
            _report('ERROR', f'Failed to restore scene from snapshot: {e}')
            return False

        # Rebuild commit UI list & restore selection
        try:
            wm['gitblend_loading_history'] = True
            populate_ui_from_metadata(context)
        finally:
            try:
                if 'gitblend_loading_history' in wm:
                    del wm['gitblend_loading_history']
            except Exception:
                pass
        try:
            props_after = getattr(context.scene, 'gitblend_props', None)
            if props_after:
                for i, c in enumerate(props_after.commits):
                    if c.hash == target_hash:
                        props_after.commits_index = i
                        break
        except Exception:
            pass
            
        _report('INFO', f'Checked out commit {target_hash[:8]} -> scene restored from {snapshot_name}')
        return True
    
    finally:
        # Always release the checkout lock
        if 'gitblend_checkout_in_progress' in wm:
            del wm['gitblend_checkout_in_progress']
        if 'gitblend_checkout_in_progress' in wm:
            del wm['gitblend_checkout_in_progress']


class GITBLEND_OT_checkout(bpy.types.Operator):
    bl_idname = "gitblend.checkout"
    bl_label = "Checkout Commit"
    bl_description = "Restore the scene to the selected commit by replacing current scene data"
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