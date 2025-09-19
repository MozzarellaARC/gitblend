import bpy # type: ignore
from ..main.initialize import check_initialized_status


class GITBLEND_UL_commit_history(bpy.types.UIList):
    """UIList for displaying commit history"""
    bl_idname = "GITBLEND_UL_commit_history"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        commit = item
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            # Short hash
            short_hash = commit.hash[:8] if commit.hash else "<none>"
            row.label(text=short_hash, icon='FILE_BLEND')
            
            # Timestamp (if available)
            if commit.timestamp:
                # Format timestamp for display
                try:
                    from datetime import datetime
                    # Handle both ISO format and simple timestamp
                    if 'T' in commit.timestamp:
                        dt = datetime.fromisoformat(commit.timestamp.replace('Z', '+00:00'))
                    else:
                        # Fallback for other formats
                        dt = datetime.strptime(commit.timestamp[:19], "%Y-%m-%d %H:%M:%S")
                    time_str = dt.strftime("%m/%d %H:%M")
                except Exception:
                    # Fallback to first 16 characters
                    time_str = commit.timestamp[:16] if len(commit.timestamp) >= 16 else commit.timestamp
                row.label(text=time_str)
            else:
                row.label(text="--:--")
            
            # Message (truncated)
            message = commit.message[:40] + "..." if len(commit.message) > 40 else commit.message
            row.label(text=message)
            
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text=commit.hash[:8] if commit.hash else "?")


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

        # Repository section
        box = layout.box()
        box.label(text="Repository", icon='FILE_FOLDER')
        
        if not initialized:
            box.label(text="Not initialized", icon='ERROR')
            box.operator("gitblend.initialize", text="Initialize Git Blend", icon='PLUS')
        else:
            box.label(text="Initialized", icon='CHECKMARK')
            box.operator("gitblend.refresh_history", text="Refresh", icon='FILE_REFRESH')
        
        # Commit section
        layout.separator()
        commit_box = layout.box()
        commit_box.label(text="Commit", icon='FILE_TICK')
        
        commit_box.prop(props, "commit_message", text="Message")
        
        if initialized:
            commit_box.operator("gitblend.commit", text="Commit Changes", icon='FILE_TICK')
        else:
            commit_box.label(text="Initialize repository first", icon='INFO')
        
        # History section
        layout.separator()
        history_box = layout.box()
        history_box.label(text="History", icon='TIME')
        
        if initialized and props.commits:
            # Show commit history UIList
            history_box.template_list(
                "GITBLEND_UL_commit_history", "", 
                props, "commits", 
                props, "commits_index", 
                rows=5
            )
            
            # Show details of selected commit
            if 0 <= props.commits_index < len(props.commits):
                selected_commit = props.commits[props.commits_index]
                
                # Show commit details (checkout happens automatically on selection)
                details_row = history_box.row()
                details_row.label(text=f"Selected: {selected_commit.hash[:8]}", icon='FILE_BLEND')
                
        elif initialized:
            history_box.label(text="No commits yet", icon='INFO')
        else:
            history_box.label(text="Initialize repository to see history", icon='INFO')