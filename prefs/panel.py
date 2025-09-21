import bpy

class GITBLEND_UL_History_List(bpy.types.UIList):
    """UIList to display commit items"""
    bl_idname = "GITBLEND_UL_commit_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        commit = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Split layout for message and timestamp
            split = layout.split(factor=0.5)
            split.prop(commit, "message", text="", emboss=False, icon='FILE_TICK')
            split.label(text=commit.timestamp, icon='TIME')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE_TICK')

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
        row0.operator("gitblend.commit", text="Commit Changes", icon='FILE_TICK')

        row2 = layout.row()
        row2.template_list(listtype_name="GITBLEND_UL_commit_list",
                           list_id="commit_history",
                           dataptr=scene, 
                           propname="commit_history",
                           active_dataptr=scene,
                           active_propname="i",
                           type='DEFAULT')
        
        # Add action buttons column next to the list
        col = row2.column()
        col.operator("gitblend.refresh", text="", icon='FILE_REFRESH')
        col.operator("gitblend.checkout", text="", icon='IMPORT')
        