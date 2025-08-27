import bpy

class GITBLEND_Panel(bpy.types.Panel):
    bl_idname = "GB_PT_main_panel"
    bl_label = "Git Blend Main Panel"
    bl_category = "Git Blend"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Git Blend"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        gitblend_props = getattr(scene, "gitblend_props", None)
        box = layout.box()

        if not gitblend_props:
            layout.label(text="GITBLEND properties not registered.")
            return

        # Initialize controls
        row = layout.row(align=True)
        row.operator("gitblend.initialize", text="Initialize", icon='FILE_NEW')

        col = layout.column(align=True)
        col.label(text="Save Events:")
        if len(gitblend_props.save_events) == 0:
            col.label(text="No saves recorded yet.", icon='INFO')
        else:
            box = col.box()
            for i, ev in enumerate(gitblend_props.save_events[-50:]):  # show last 50
                row = box.row()
                row.label(text=f"{i+1}. {ev.timestamp}")
                # Filepath display removed per request

        row = layout.row(align=True)
        row.operator("gitblend.clear_save_log", text="Clear Log", icon='TRASH')


def register_panel():
    bpy.utils.register_class(GITBLEND_Panel)

def unregister_panel():
    bpy.utils.unregister_class(GITBLEND_Panel)