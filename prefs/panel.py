import bpy # type: ignore
from .constants import BLEND_GIT_DIR_NAME
from pathlib import Path

class GITBLEND_UL_commit_history(bpy.types.UIList):
    """UIList to display commit history."""
    bl_idname = "GITBLEND_UL_commit_history"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        pass

class GITBLEND_PT_Panel(bpy.types.Panel):
    """Panel for Git Blend preferences."""
    bl_label = "Git Blend"
    bl_idname = "GITBLEND_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Git Blend'

    def draw(self, context):
        pass