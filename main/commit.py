import bpy
import hashlib
import os
import time
from pathlib import Path


def _compute_scene_hash(scene: bpy.types.Scene) -> str:
    """Compute a sha-256 hash representing the current scene state.
    For now we use a combination of object names, modification times and a timestamp
    to ensure uniqueness. This can evolve into a deterministic content hash later.
    """
    h = hashlib.sha256()
    # Basic entropy: object names and counts
    try:
        for obj in scene.objects:
            h.update(obj.name.encode('utf-8', 'ignore'))
            h.update(str(obj.type).encode())
    except Exception:
        pass
    # Add current time to guarantee uniqueness even if scene unchanged
    h.update(str(time.time_ns()).encode())
    return h.hexdigest()


class GITBLEND_OT_commit(bpy.types.Operator):
    bl_idname = "gb.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit changes to the Git repository"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = getattr(context.scene, "gitblend_props", None)
        commit_message = (props.commit_message if props else "").strip()

        if not commit_message:
            self.report({'ERROR'}, "Commit message cannot be empty.")
            return {'CANCELLED'}
        # Determine current working .blend file path
        current_filepath = bpy.data.filepath
        if not current_filepath:
            self.report({'ERROR'}, "Please save the .blend file before committing.")
            return {'CANCELLED'}

        current_dir = Path(current_filepath).resolve().parent
        gitblend_dir = current_dir / '.gitblend'
        try:
            gitblend_dir.mkdir(exist_ok=True)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create .gitblend directory: {e}")
            return {'CANCELLED'}

        # Compute a unique sha-256 filename
        scene_hash = _compute_scene_hash(context.scene)
        snapshot_path = gitblend_dir / f"{scene_hash}.blend"

        # Save snapshot without altering the currently open file (copy=True)
        try:
            bpy.ops.wm.save_as_mainfile(filepath=str(snapshot_path), copy=True)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save snapshot: {e}")
            return {'CANCELLED'}

        # TODO: Extend with metadata/commit log indexing.
        self.report({'INFO'}, f"Committed snapshot {snapshot_path.name} : {commit_message}")
        return {'FINISHED'}