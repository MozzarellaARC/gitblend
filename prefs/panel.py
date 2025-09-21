import bpy

class GITBLEND_UL_History_List(bpy.types.UIList):
    """UIList to display commit items"""
    bl_idname = "GITBLEND_UL_commit_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        self.layout.type = 'GRID'

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
        row0.prop(scene, "message", icon='TEXT', text='')
        row1 = layout.row()
        row1.operator("gitblend.commit", text="Commit Changes", icon='FILE_TICK')

        row2 = layout.row()
        row2.template_list(listtype_name="GITBLEND_UL_History_List",
                           list_id="gitblend_props_list",
                           dataptr=scene, 
                           propname="gitblend_props",
                           active_dataptr=scene,
                           active_propname="gitblend_props_index")