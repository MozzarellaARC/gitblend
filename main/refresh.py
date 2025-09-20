"""Operators for refreshing git_blend data."""
import bpy
import time
from datetime import datetime
from .utils import get_gitblend_dir, load_commit_metadata


class GITBLEND_OT_RefreshCommits(bpy.types.Operator):
    """Refresh the commit list."""
    bl_idname = "gitblend.refresh_commits"
    bl_label = "Refresh Commits"
    bl_description = "Refresh the commit list from git_blend metadata"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        try:
            gitblend_dir = get_gitblend_dir()
            if not gitblend_dir.exists():
                self.report({'WARNING'}, "Git Blend not initialized.")
                return {'CANCELLED'}
            
            metadata = load_commit_metadata(gitblend_dir)
            commits = metadata.get("commits", {})
            current_commit = metadata.get("current_commit")
            
            # Clear existing commits
            context.scene.gitblend.commits.clear()
            
            # Sort commits by timestamp (newest first)
            sorted_commits = sorted(
                commits.items(), 
                key=lambda x: x[1].get("timestamp", 0), 
                reverse=True  # Newest first (top to bottom)
            )
            
            # Add commits to the property collection
            for commit_hash, commit_data in sorted_commits:
                item = context.scene.gitblend.commits.add()
                item.hash = commit_hash
                item.message = commit_data.get("message", "No message")
                
                # Store timestamp for sorting
                timestamp = commit_data.get("timestamp", 0)
                item.timestamp_float = timestamp
                
                # Format timestamp for display
                if isinstance(timestamp, (int, float)) and timestamp > 0:
                    try:
                        dt = datetime.fromtimestamp(timestamp)
                        item.timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        item.timestamp = str(timestamp)
                else:
                    item.timestamp = "Unknown"
                
                item.is_current = (commit_hash == current_commit)
                
                # Set active index to current commit
                if item.is_current:
                    context.scene.gitblend.active_commit_index = len(context.scene.gitblend.commits) - 1
            
            self.report({'INFO'}, f"Refreshed {len(commits)} commits")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to refresh commits: {str(e)}")
            return {'CANCELLED'}


class GITBLEND_OT_CheckoutSelected(bpy.types.Operator):
    """Checkout the selected commit."""
    bl_idname = "gitblend.checkout_selected"
    bl_label = "Checkout Selected"
    bl_description = "Checkout the currently selected commit"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        commits = context.scene.gitblend.commits
        active_index = context.scene.gitblend.active_commit_index
        
        if active_index < 0 or active_index >= len(commits):
            self.report({'ERROR'}, "No commit selected")
            return {'CANCELLED'}
        
        selected_commit = commits[active_index]
        
        # Call the checkout operator
        bpy.ops.gitblend.checkout(commit_hash=selected_commit.hash)
        
        # Refresh the commit list to update current status
        bpy.ops.gitblend.refresh_commits()
        
        return {'FINISHED'}