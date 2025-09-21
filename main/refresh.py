import bpy

class GITBLEND_OT_Refresh(bpy.types.Operator):
    bl_idname = "gitblend.refresh"
    bl_label = "Refresh Commits"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pass