import bpy # type: ignore
from ..main.initialize import check_initialized_status


class GITBLEND_Panel(bpy.types.Panel):
    bl_label = "Git Blend"
    bl_idname = "GITBLEND_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Git Blend'

    def draw(self, context):
        layout = self.layout
        props = context.scene.gitblend_props

        # Check initialization status (read-only, safe in draw method)
        initialized = check_initialized_status(context)

        layout.prop(props, "commit_message", text="Commit Message")
        if not initialized:
            layout.operator("gitblend.initialize", text="Initialize Git Blend", icon='FILE_FOLDER')
        if initialized:
            layout.operator("gitblend.commit", text="Commit Changes", icon='FILE_TICK')