import bpy

class GITBLEND_Panel(bpy.types.Panel):
    bl_idname = "GB_PT_main_panel"
    bl_label = "Git Blend Main Panel"
    bl_category = "Git Blend"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

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
        col.label(text="Save Events (recent):")
        if len(gitblend_props.save_events) == 0:
            col.label(text="No saves recorded yet.", icon='INFO')
        else:
            ev_box = col.box()
            for i, ev in enumerate(gitblend_props.save_events[-50:]):  # show last 50
                row = ev_box.row()
                row.label(text=f"{i+1}. {ev.timestamp}")

        # Change log section
        col = layout.column(align=True)
        col.label(text="Change Log (recent):")
        if len(gitblend_props.changes_log) == 0:
            col.label(text="No commits yet.", icon='INFO')
        else:
            log_box = col.box()
            for i, entry in enumerate(gitblend_props.changes_log[-100:]):  # show last 100
                row = log_box.row()
                row.label(text=f"{i+1}. {entry.timestamp} - {entry.message}")

        # Dynamic string list section
        col = layout.column(align=True)
        col.label(text="String List:")
        list_box = col.box()
        # Show each item as editable row
        if len(gitblend_props.string_items) == 0:
            list_box.label(text="No items.", icon='INFO')
        else:
            for i, item in enumerate(gitblend_props.string_items):
                row = list_box.row(align=True)
                row.prop(item, "name", text=f"{i+1}")
                op = row.operator("gitblend.string_remove", text="", icon='X')
                op.index = i
        # Controls
        row = col.row(align=True)
        row.operator("gitblend.string_add", text="Add", icon='ADD')

        # Dropdown showing the dynamic list
        col = layout.column(align=True)
        col.label(text="Dropdown:")
        col.prop(gitblend_props, "selected_string", text="")
        # Optional: show the chosen value
        if gitblend_props.selected_string not in {"", "-1"}:
            try:
                idx = int(gitblend_props.selected_string)
                if 0 <= idx < len(gitblend_props.string_items):
                    col.label(text=f"Selected: {gitblend_props.string_items[idx].name}")
            except Exception:
                pass

    # No clear actions per request


def register_panel():
    bpy.utils.register_class(GITBLEND_Panel)

def unregister_panel():
    try:
        bpy.utils.unregister_class(GITBLEND_Panel)
    except RuntimeError:
        pass