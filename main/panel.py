import bpy
from .utils import get_selected_branch
from .validate import get_dotgitblend_collection


class GITBLEND_UL_ChangeLog(bpy.types.UIList):
    bl_idname = "GITBLEND_UL_ChangeLog"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            msg = getattr(item, "message", "") or "<no message>"
            ts = getattr(item, "timestamp", "?")
            layout.label(text=f"{index + 1}. {ts} - {msg}")
        elif self.layout_type == "GRID":
            layout.alignment = 'CENTER'
            layout.label(text=str(index + 1))


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
        has_gitblend = get_dotgitblend_collection(scene) is not None
        layout.label(icon='CHECKMARK' if has_gitblend else 'ERROR')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = getattr(scene, "gitblend_props", None)
        if not props:
            layout.label(text="GITBLEND properties not registered.")
            return

        has_gitblend = get_dotgitblend_collection(scene) is not None

        row = layout.row(align=True)
        row.operator("gitblend.initialize", text="Initialize", icon='FILE_NEW')
        row = layout.row(align=True)
        row.alignment = 'RIGHT'
        row.label(text=f"Branch: {get_selected_branch(props)}")
        if not has_gitblend:
            layout.label(text="'.gitblend' not found. Click Initialize.", icon='INFO')

        box = layout.box()
        header = box.row()
        header.prop(props, "ui_show_commit", icon='TRIA_DOWN' if props.ui_show_commit else 'TRIA_RIGHT', icon_only=True, emboss=False)
        header.label(text="Commit")
        if props.ui_show_commit:
            col = box.column(align=False)
            col.prop(props, "commit_message", text="Message", icon='TEXT')
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

        box = layout.box()
        header = box.row()
        header.prop(props, "ui_show_branches", icon='TRIA_DOWN' if props.ui_show_branches else 'TRIA_RIGHT', icon_only=True, emboss=False)
        header.label(text="Branches")
        if props.ui_show_branches:
            row = box.row(align=True)
            row.prop(props, "selected_string", text="")
            sub = row.row(align=True)
            sub.enabled = has_gitblend
            sub.operator("gitblend.string_add", text="", icon='ADD')
            sub.operator("gitblend.string_remove", text="", icon='REMOVE')

        box = layout.box()
        header = box.row()
        header.prop(props, "ui_show_log", icon='TRIA_DOWN' if props.ui_show_log else 'TRIA_RIGHT', icon_only=True, emboss=False)
        header.label(text="Change Log")
        if props.ui_show_log:
            if len(props.changes_log) == 0:
                box.label(text="No commits yet.", icon='INFO')
            else:
                box.template_list(
                    "GITBLEND_UL_ChangeLog",
                    "",
                    props,
                    "changes_log",
                    props,
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