import bpy

class YANT_Panel(bpy.types.Panel):
    bl_idname = "BGIT_PT_main_panel"
    bl_label = "Blender Git Main Panel"
    bl_category = "Blender Git"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Blender Git"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        yant_props = getattr(scene, "yant_props", None)

        if not yant_props:
            layout.label(text="YANT properties not registered.")
            return

        col = layout.column(align=True)
        col.label(text="Save Events:")
        if len(yant_props.save_events) == 0:
            col.label(text="No saves recorded yet.", icon='INFO')
        else:
            box = col.box()
            for i, ev in enumerate(yant_props.save_events[-50:]):  # show last 50
                row = box.row()
                row.label(text=f"{i+1}. {ev.timestamp}")
                if ev.filepath:
                    row.label(text=ev.filepath, icon='FILE_BLEND')

        row = layout.row(align=True)
        row.operator("yant.clear_save_log", text="Clear Log", icon='TRASH')
        row.operator("yant.add_dummy_event", text="Add Test", icon='PLUS')


def register_panel():
    bpy.utils.register_class(YANT_Panel)

def unregister_panel():
    bpy.utils.unregister_class(YANT_Panel)