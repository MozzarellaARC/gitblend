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
        gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"

        if not bpy.data.filepath:
            self.report({'ERROR'}, "Please save the current Blender file before committing.")
            return {'CANCELLED'}

        commit_exists = list(gitblend_dir.glob("*.blend"))
        if commit_exists:
            refresh_commit_history(context)
            self.report({'INFO'}, "Commits found in .gitblend, synchronize with existing history")
            return {'CANCELLED'}

        # Placeholder scene properties access
        # scene = context.scene.gitblend_props

        selected = context.selected_objects
        name = context.active_object.name

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

        
        
        