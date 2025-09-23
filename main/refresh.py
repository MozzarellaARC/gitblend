from webbrowser import get
import bpy
import os
from pathlib import Path
import re
import json

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
    
    # Load commits from commits.json
    commits_file = gitblend_dir / "commits.json"
    if not commits_file.exists():
        return
    
    try:
        with open(commits_file, 'r') as f:
            commits_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return
    
    # Get commits list and sort by creation time (newest first)
    commit_list = commits_data.get("commits", [])
    commit_list.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    
    # Add commits to the collection
    for commit_data in commit_list:
        commit_item = scene.commit_history.add()
        commit_item.message = commit_data.get("uid", "unknown")  # Use UID as message
        commit_item.timestamp = commit_data.get("timestamp", "")
        commit_item.uid = commit_data.get("uid", "")
        commit_item.filename = f"{commit_data.get('uid', 'unknown')}_{commit_data.get('timestamp', '')}"
        
        # Calculate file size of the objects directory
        objects_dir = gitblend_dir / "objects" / commit_data.get("uid", "")
        if objects_dir.exists():
            total_size = sum(f.stat().st_size for f in objects_dir.rglob('*') if f.is_file())
            commit_item.file_size = total_size
        else:
            commit_item.file_size = 0
        
        # Calculate hash (optional - could be expensive for large files)
        # For now, we'll use a simple hash of the uid + size as placeholder
        import hashlib
        content = f"{commit_data.get('uid', 'unknown')}{commit_item.file_size}".encode('utf-8')
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
    
