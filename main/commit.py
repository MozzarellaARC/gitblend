from bz2 import compress
import bpy
from pathlib import Path

class GITBLEND_OT_Commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit current changes to .gitblend repository"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene.gitblend_props
        selected = bpy.context.selected_objects

        # Directory setup
        gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"
        gitblend_dir.mkdir(parents=True, exist_ok=True)

        # Export selected objects to a .blend file in the .gitblend directory
        bpy.data.libraries.write(
            filepath=str(gitblend_dir / f"{scene.commit_message}.blend"),
            datablocks=set(selected),
            fake_user=True,
            compress=True,
        )
        return {'FINISHED'}