import bpy
from ..utils.utils import get_selected_branch

class GITBLEND_UL_ChangeLog(bpy.types.UIList):
    bl_idname = "GITBLEND_UL_ChangeLog"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0):
        # item is a GITBLEND_ChangeLogEntry
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            # Show: <date> <branch> <commit-message>
            msg = (getattr(item, "message", "") or "").strip() or "<no message>"
            ts = getattr(item, "timestamp", "?")
            # Extract date only
            try:
                date_only = ts.split()[0] if isinstance(ts, str) and ts else str(ts)
            except Exception:
                date_only = str(ts)
            br = (getattr(item, "branch", "") or "").strip() or "main"
            layout.label(text=f"{date_only} {br} {msg}")
        elif self.layout_type == "GRID":
            layout.alignment = 'CENTER'
            layout.label(text=str(index+1))

    def filter_items(self, context, data, propname):
        # Filter to show only entries for the current branch
        items = getattr(data, propname, [])
        try:
            current_branch = get_selected_branch(data)
        except Exception:
            current_branch = "main"
        flt_flags = [0] * len(items)
        bf = self.bitflag_filter_item
        for i, it in enumerate(items):
            br = (getattr(it, "branch", "") or "").strip() or "main"
            if br == current_branch:
                flt_flags[i] = bf
        return flt_flags, []

class GITBLEND_Panel(bpy.types.Panel):
    bl_idname = "GB_PT_main_panel"
    bl_label = "Git Blend"
    bl_category = "Git Blend"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        layout = self.layout
        scene = context.scene
        # Detect gitblend presence for UI state
        has_gitblend = (bpy.data.scenes.get("gitblend") or bpy.data.scenes.get(".gitblend")) is not None
        layout.label(icon='CHECKMARK' if has_gitblend else 'ERROR')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        gitblend_props = getattr(scene, "gitblend_props", None)
        if not gitblend_props:
            layout.label(text="GITBLEND properties not registered.")
            return

        # Detect gitblend presence for UI state
        has_gitblend = (bpy.data.scenes.get("gitblend") or bpy.data.scenes.get(".gitblend")) is not None

        # Top row: Initialize left, current branch right
        row = layout.row(align=True)
        row.operator("gitblend.initialize", text="Initialize", icon='FILE_NEW')
        row = layout.row(align=True)
        row.alignment = 'RIGHT'
        row.label(text=f"Branch: {get_selected_branch(gitblend_props)}")
        if not has_gitblend:
            layout.label(text="'gitblend' Scene not found. Click Initialize.", icon='INFO')

        # Commit (collapsible)
        box = layout.box()
        header = box.row()
        header.prop(gitblend_props, "ui_show_commit", icon='TRIA_DOWN' if gitblend_props.ui_show_commit else 'TRIA_RIGHT', icon_only=True, emboss=False)
        header.label(text="Commit")
        if gitblend_props.ui_show_commit:
            col = box.column(align=False)
            col.prop(gitblend_props, "commit_message", text="Message", icon='TEXT')
            col.separator()
            row = col.row(align=True)
            row.enabled = has_gitblend
            row.operator("gitblend.commit", text="Commit", icon='CHECKMARK')
            if not has_gitblend:
                col.label(text="Initialize first to enable committing.", icon='INFO')
            col.separator()
            row = col.row(align=False)
            row.operator("gitblend.undo_commit", text="Undo", icon='LOOP_BACK')
            row.operator("gitblend.discard_changes", text="Discard", icon='X')

        # Branches (collapsible)
        box = layout.box()
        header = box.row()
        header.prop(gitblend_props, "ui_show_branches", icon='TRIA_DOWN' if gitblend_props.ui_show_branches else 'TRIA_RIGHT', icon_only=True, emboss=False)
        header.label(text="Branches")
        if gitblend_props.ui_show_branches:
            row = box.row(align=True)
            row.prop(gitblend_props, "selected_string", text="")
            sub = row.row(align=True)
            sub.enabled = has_gitblend
            sub.operator("gitblend.string_add", text="", icon='ADD')
            sub.operator("gitblend.string_remove", text="", icon='REMOVE')

        # Change Log (collapsible + scrollable)
        box = layout.box()
        header = box.row()
        header.prop(gitblend_props, "ui_show_log", icon='TRIA_DOWN' if gitblend_props.ui_show_log else 'TRIA_RIGHT', icon_only=True, emboss=False)
        header.label(text="Change Log")
        if gitblend_props.ui_show_log:
            if len(gitblend_props.changes_log) == 0:
                box.label(text="No commits yet.", icon='INFO')
            else:
                box.template_list(
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