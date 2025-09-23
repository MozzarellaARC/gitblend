from os import mkdir
import bpy
from pathlib import Path
import time
import uuid
from .refresh import refresh_commit_history

class GITBLEND_OT_Commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit current changes to .gitblend repository"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene.gitblend_props

        # Ensure save
        if not bpy.data.filepath:
            self.report({'ERROR'}, "Please save the current Blender file before committing.")
            return {'CANCELLED'}

        # Ensure .gitblend directory exists
        gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"
        if not gitblend_dir.exists():
            mkdir(gitblend_dir)

        # If .gitblend exists and there are commits, proceed to sync
        if gitblend_dir.exists() and any(gitblend_dir.iterdir()):
            self.report({'WARNING'}, ".gitblend commit history exists proceed to synchronize.")
            refresh_commit_history(context)
            return {'CANCELLED'}

        selected = context.selected_objects
        name = context.active_object.name

        if not selected:
            self.report({'ERROR'}, "No objects selected for commit")
            return {'CANCELLED'}

        # Directory setup
        gitblend_dir.mkdir(parents=True, exist_ok=True)

        # Export selected objects to a .blend file in the .gitblend directory
        timestamp = time.strftime("%y-%m-%d")
        uid = str(uuid.uuid4())[:8]
        filename = f"{name}_{timestamp}_{uid}.blend"

        # Invoke libraries.write module to save selected objects
        bpy.data.libraries.write(
            filepath=str(gitblend_dir / filename),
            datablocks=set(selected),
            fake_user=True,
            compress=True,
        )

        # Refresh commit history to show the new commit
        refresh_commit_history(context)
        return {'FINISHED'}

        
        
        