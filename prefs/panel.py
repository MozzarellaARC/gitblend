import bpy  # type: ignore


class GITBLEND_UL_CommitHistory(bpy.types.UIList):
    """UIList to display commit history entries."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):  # noqa: D401
        commit = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            # Show short hash and first part of message
            short_hash = commit.hash[:7] if commit.hash else "<none>"
            row.label(text=short_hash)
            msg = commit.message if len(commit.message) < 50 else commit.message[:47] + '...'
            row.label(text=msg, icon='FILE_BLEND')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=commit.hash[:7] if commit.hash else "?")

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
        col.prop(props, "commit_message", text="Commit Message")
        col.operator("gb.commit", text="Commit Changes", icon='FILE_TICK')

        layout.separator()
        header = layout.row()
        header.label(text="Commit History")
        header.operator("gb.refresh_commit_history", text="", icon='FILE_REFRESH')

        row = layout.row()
        row.template_list(
            "GITBLEND_UL_CommitHistory",
            "commit_history",
            props,
            "commit_history",
            props,
            "commit_history_index",
            rows=6,
        )

        if props.commit_history and 0 <= props.commit_history_index < len(props.commit_history):
            selected = props.commit_history[props.commit_history_index]
            box = layout.box()
            box.label(text=f"Hash: {selected.hash}")
            box.label(text=f"Author: {selected.author}")
            box.label(text=f"Date: {selected.date}")
            box.label(text=f"Message: {selected.message}")