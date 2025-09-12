import bpy
from . import blend_serialization

class GITBLEND_OT_commit(bpy.types.Operator):
    bl_idname = "gb.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit changes to the Git repository"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gitblend_props
        commit_message = props.commit_message.strip()

        if not commit_message:
            self.report({'ERROR'}, "Commit message cannot be empty.")
            return {'CANCELLED'}

        blend_serialization.export_json()

        self.report({'INFO'}, f"Committed with message: {commit_message}")
        return {'FINISHED'}