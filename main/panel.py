import bpy

class YANT_Panel(bpy.types.Panel):
    bl_idname = "YANT_PT_main_panel"
    bl_label = "YANT Main Panel"
    bl_category = "YANT"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = "objectmode"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        yant_props = scene.yant_props


def register_panel():
    bpy.utils.register_class(YANT_Panel)

def unregister_panel():
    bpy.utils.unregister_class(YANT_Panel)