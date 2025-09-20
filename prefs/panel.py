import bpy # type: ignore
from .constants import GITBLEND_DIR_NAME
from pathlib import Path

class GITBLEND_UL_commit_history(bpy.types.UIList):
    """UIList to display commit history."""
    bl_idname = "GITBLEND_UL_commit_history"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Display commit info
            split = layout.split(factor=0.7)
            
            # Hash (shortened)
            col = split.column()
            col.label(text=f"{item.hash[:8]}")
            
            # Timestamp
            col = split.column()
            col.label(text=item.timestamp)

            # Commit message
            split.label(text=f"{item.message}")
        
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE_BLEND')

class GITBLEND_PT_Panel(bpy.types.Panel):
    """Panel for Git Blend preferences."""
    bl_label = "Git Blend"
    bl_idname = "GITBLEND_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Git Blend'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Check if git_blend is initialized
        blend_dir = Path(bpy.data.filepath).parent if bpy.data.filepath else None
        gitblend_dir = blend_dir / GITBLEND_DIR_NAME if blend_dir else None
        is_initialized = gitblend_dir and gitblend_dir.exists()
        
        # Header info
        if bpy.data.filepath:
            layout.label(text=f"File: {Path(bpy.data.filepath).name}")
        else:
            layout.label(text="File: Not saved", icon='ERROR')
        
        if is_initialized:
            layout.label(text="Status: Initialized", icon='CHECKMARK')
        else:
            layout.label(text="Status: Not initialized", icon='X')
        
        layout.separator()
        
        # Main operations
        if not bpy.data.filepath:
            layout.label(text="Save the .blend file first", icon='INFO')
            return
        
        if not is_initialized:
            # Initialize section
            box = layout.box()
            box.label(text="Initialize Git Blend", icon='PLUS')
            box.operator("gitblend.initialize", text="Initialize", icon='PLAY')
        else:
            # Main git operations
            col = layout.column(align=True)
            
            # Commit section
            box = layout.box()
            box.label(text="Commit Changes", icon='FILE_TICK')
            # Add commit message input
            box.prop(scene.gitblend, "commit_message", text="Message")
            box.operator("gitblend.commit", text="Commit", icon='PLUS')
            
            # Commit history section
            box = layout.box()
            box.label(text="Commit History", icon='TIME')
            
            # Refresh button
            row = box.row()
            row.operator("gitblend.refresh_commits", text="Refresh", icon='FILE_REFRESH')
            row.operator("gitblend.list_commits", text="List in Console", icon='CONSOLE')
            
            # UIList for commits
            if hasattr(scene, 'gitblend'):
                box.template_list(
                    "GITBLEND_UL_commit_history", 
                    "", 
                    scene.gitblend, 
                    "commits",
                    scene.gitblend, 
                    "active_commit_index",
                    rows=5
                )
                
                # Checkout button
                if scene.gitblend.commits:
                    box.operator("gitblend.checkout_selected", text="Checkout Selected", icon='IMPORT')
            else:
                box.label(text="Properties not available")
        
        # Utility section
        layout.separator()
        col = layout.column(align=True)
        col.label(text="Utilities", icon='TOOL_SETTINGS')
        if is_initialized:
            col.operator("gitblend.list_commits", text="List Commits", icon='TEXT')