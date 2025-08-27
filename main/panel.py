import bpy

class GITBLEND_UL_ChangeLog(bpy.types.UIList):
    bl_idname = "GITBLEND_UL_ChangeLog"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0):
        # item is a GITBLEND_ChangeLogEntry
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            # Show index and concise message
            msg = getattr(item, "message", "") or "<no message>"
            ts = getattr(item, "timestamp", "?")
            layout.label(text=f"{index+1}. {ts} - {msg}")
        elif self.layout_type == "GRID":
            layout.alignment = 'CENTER'
            layout.label(text=str(index+1))

class GITBLEND_Panel(bpy.types.Panel):
    bl_idname = "GB_PT_main_panel"
    bl_label = "Git Blend"
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

        # Detect .gitblend presence for UI state
        has_gitblend = any(c.name == ".gitblend" for c in scene.collection.children)

        # Initialize controls
        row = layout.row(align=True)
        row.operator("gitblend.initialize", text="Initialize", icon='FILE_NEW')

        # Commit input and action
        box = layout.box()
        col = box.column(align=False)
        col.label(text="Commit Message:")
        col.prop(gitblend_props, "commit_message", text="")
        row = col.row(align=False)
        row.enabled = has_gitblend
        row.operator("gitblend.commit", text="Commit", icon='CHECKMARK')
        if not has_gitblend:
            col.label(text="Initialize first to enable committing.", icon='INFO')

        # Branch selection and quick add
        col = layout.column(align=True)
        col.label(text="Branch:")
        row = col.row(align=False)
        row.prop(gitblend_props, "selected_string", text="")
        row.operator("gitblend.string_add", text="Branch", icon='ADD')

        # Change log section (scrollable)
        col = layout.column(align=True)
        col.label(text="Change Log:")
        if len(gitblend_props.changes_log) == 0:
            col.label(text="No commits yet.", icon='INFO')
        else:
            col.template_list(
                "GITBLEND_UL_ChangeLog",
                "",
                gitblend_props,
                "changes_log",
                gitblend_props,
                "changes_log_index",
                rows=7,
            )

def register_panel():
    bpy.utils.register_class(GITBLEND_UL_ChangeLog)
    bpy.utils.register_class(GITBLEND_Panel)

def unregister_panel():
    try:
        bpy.utils.unregister_class(GITBLEND_Panel)
    except RuntimeError:
        pass
    try:
        bpy.utils.unregister_class(GITBLEND_UL_ChangeLog)
    except RuntimeError:
        pass