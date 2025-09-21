import bpy # type: ignore
from .constants import GITBLEND_DIR_NAME
from pathlib import Path

class GITBLEND_PT_Panel(bpy.types.Panel):
    """Panel for Git Blend preferences."""
    bl_label = "Git Blend"
    bl_idname = "GITBLEND_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Git Blend'

    def draw(self, context):
        pass