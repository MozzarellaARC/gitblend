import bpy

class GITBLEND_OT_checkout(bpy.types.Operator):
    bl_idname = "gitblend.checkout"
    bl_label = "Checkout Commit"
    bl_description = "Checkout the selected commit"

    def execute(self, context):
        pass