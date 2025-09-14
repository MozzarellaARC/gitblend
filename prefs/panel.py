import bpy # type: ignore

class GITBLEND_UL_commit_history(bpy.types.UIList):
    """UIList showing commit history entries."""
    bl_idname = "GITBLEND_UL_commit_history"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):  # noqa: D401
        commit = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            # Truncate hash for display
            short_hash = commit.hash[:8] if commit.hash else "<none>"
            row.label(text=short_hash, icon='FILE_BLEND')
            row.label(text=commit.message[:60])
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=commit.hash[:8])

    def filter_items(self, context, data, propname):  # noqa: D401
        # No filtering yet
        items = getattr(data, propname)
        flt_flags = [self.bitflag_filter_item] * len(items)
        flt_neworder = []
        return flt_flags, flt_neworder


class GITBLEND_Panel(bpy.types.Panel):
    bl_idname = "GB_PT_main_panel"
    bl_label = "Git Blend"
    bl_category = ".gitblend"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        props = context.scene.gitblend_props
        col = layout.column(align=True)
        col.label(text="Commit History:")
        col.template_list("GITBLEND_UL_commit_history", "", props, "commits", props, "commits_index", rows=5)

        box = layout.box()
        box.prop(props, "commit_message", text="Message")
        row = box.row(align=True)
        row.operator("gb.commit", text="Commit", icon='FILE_TICK')
        # Future buttons: diff, checkout etc.

        layout.separator()
        layout.operator("gb.bpy_serde", text="Serialize bpy into json", icon='DUPLICATE')