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

        bpy.data.libraries.write(
            filepath=str(Path(bpy.data.filepath).parent / f"{scene.commit_message}.blend"),
            datablocks=set(selected),
            fake_user=True,
        )
        return {'FINISHED'}