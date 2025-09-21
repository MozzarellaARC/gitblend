import bpy

class GITBLEND_OT_Checkout(bpy.types.Operator):
    """Checkout a specific commit"""
    bl_idname = "gitblend.checkout"
    bl_label = "Checkout Commit"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.data.libraries.load("path_to_your_gitblend_file.blend", link=False)
        pass