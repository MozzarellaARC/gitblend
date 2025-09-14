import bpy
from datetime import datetime
import uuid


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

        # Placeholder: real commit logic would serialize and store scene changes.
        
        self.report({'INFO'}, f"Committed with message: {commit_message}")
        return {'FINISHED'}