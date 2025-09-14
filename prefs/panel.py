import bpy # type: ignore


class GITBLEND_Panel(bpy.types.Panel):
    bl_idname = "GB_PT_main_panel"
    bl_label = "Git Blend"
    bl_category = ".gitblend"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        props = context.scene.gitblend_props

        layout.prop(props, "commit_message", text="Commit Message")
        layout.operator("gb.commit", text="Commit Changes", icon='FILE_TICK')
        layout.separator()
        col = layout.column(align=True)
        col.operator("gb.commit_copy_scene", text="Commit Copy Scene", icon='DUPLICATE')