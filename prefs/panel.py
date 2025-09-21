import bpy

class GITBLEND_PT_Panel(bpy.types.Panel):
    bl_label = "Git Blend"
    bl_idname = "GITBLEND_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Git Blend'

    def draw(self, context):
        layout = self.layout
        scene = context.scene.gitblend_props

        row0 = layout.row()
        row0.prop(scene, "commit_message", icon='TEXT', text='')
        row1 = layout.row()
        row1.operator("gitblend.commit", text="Commit Changes", icon='FILE_TICK')