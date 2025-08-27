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
        if not gitblend_props:
            layout.label(text="GITBLEND properties not registered.")
            return

        # Initialize controls
        row = layout.row(align=True)
        row.operator("gitblend.initialize", text="Initialize", icon='FILE_NEW')

        # Commit input and action
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Commit Message:")
        col.prop(gitblend_props, "commit_message", text="")
        row = col.row(align=True)
        row.operator("gitblend.commit", text="Commit", icon='CHECKMARK')

        # Save events section
        col = layout.column(align=True)
        col.label(text="Save Events:")
        if len(gitblend_props.save_events) == 0:
            col.label(text="No saves recorded yet.", icon='INFO')
        else:
            ev_box = col.box()
            for i, ev in enumerate(gitblend_props.save_events[-50:]):  # show last 50
                row = ev_box.row()
                row.label(text=f"{i+1}. {ev.timestamp}")

        # Change log section
        col = layout.column(align=True)
        col.label(text="Change Log:")
        if len(gitblend_props.changes_log) == 0:
            col.label(text="No commits yet.", icon='INFO')
        else:
            log_box = col.box()
            for i, entry in enumerate(gitblend_props.changes_log[-100:]):  # show last 100
                row = log_box.row()
                row.label(text=f"{i+1}. {entry.timestamp} - {entry.message}")

    # No clear actions per request


def register_panel():
    bpy.utils.register_class(GITBLEND_Panel)

def unregister_panel():
    bpy.utils.unregister_class(GITBLEND_Panel)