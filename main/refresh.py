from webbrowser import get
import bpy
import os
from pathlib import Path
import re

def refresh_commit_history(context):
    """Scan .gitblend directory and populate commit history"""
    scene = context.scene.gitblend_props
    
    # Clear existing commit history
    scene.commit_history.clear()
    
    # Get the .gitblend directory
    if not bpy.data.filepath:
        return
        
    gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"
    
    if not gitblend_dir.exists():
        return
    
    # Pattern to match commit files: message_timestamp_uid.blend
    commit_pattern = re.compile(r'^(.+?)_(\d{2}-\d{2}-\d{2})_([a-f0-9]{8})\.blend$')
    
    # Find all .blend files in .gitblend directory
    commit_files = []
    for file_path in gitblend_dir.glob("*.blend"):
        match = commit_pattern.match(file_path.name)
        if match:
            message, timestamp, uid = match.groups()
            commit_files.append({
                'filename': file_path.name,
                'message': message.replace('_', ' '),  # Replace underscores with spaces
                'timestamp': timestamp,
                'uid': uid,
                'mtime': file_path.stat().st_mtime  # For sorting by modification time
            })
    
    # Sort by modification time (newest first)
    commit_files.sort(key=lambda x: x['mtime'], reverse=True)
    
    # Add commits to the collection
    for commit_data in commit_files:
        commit_item = scene.commit_history.add()
        commit_item.message = commit_data['message']
        commit_item.timestamp = commit_data['timestamp']
        commit_item.uid = commit_data['uid']
        commit_item.filename = commit_data['filename']
        
        # Calculate file size
        file_path = gitblend_dir / commit_data['filename']
        if file_path.exists():
            commit_item.file_size = file_path.stat().st_size
        
        # Calculate hash (optional - could be expensive for large files)
        # For now, we'll use a simple hash of the filename + size as placeholder
        import hashlib
        content = f"{commit_data['filename']}{commit_item.file_size}".encode('utf-8')
        commit_item.hash_value = hashlib.sha256(content).hexdigest()
    
    # Reset the active index
    scene.i = 0


class GITBLEND_OT_Refresh(bpy.types.Operator):
    bl_idname = "gitblend.refresh"
    bl_label = "Refresh Commits"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        refresh_commit_history(context)
        return {'FINISHED'}
    
class GITBLEND_OT_Purge(bpy.types.Operator):
    bl_idname = "gitblend.purge"
    bl_label = "Purge Commits"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene.gitblend_props
        
        # Get the .gitblend directory
        if not bpy.data.filepath:
            self.report({'ERROR'}, "No file is currently open")
            return {'CANCELLED'}
            
        gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"
        
        if not gitblend_dir.exists():
            self.report({'WARNING'}, "No .gitblend directory found")
            return {'CANCELLED'}
        
        # Delete all .blend files in .gitblend directory
        deleted_count = 0
        for file_path in gitblend_dir.glob("*.blend"):
            try:
                file_path.unlink()
                deleted_count += 1
            except OSError as e:
                self.report({'ERROR'}, f"Failed to delete {file_path.name}: {e}")
                return {'CANCELLED'}
        
        # Clear the commit history UI
        scene.commit_history.clear()
        scene.i = 0
        
        self.report({'INFO'}, f"Purged {deleted_count} commit(s)")
        return {'FINISHED'}