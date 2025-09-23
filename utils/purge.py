import bpy
import json
import shutil
from pathlib import Path

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
        
        deleted_commit_count = 0
        deleted_file_count = 0
        
        # Check if commits.json exists and get commit count
        commits_file = gitblend_dir / "commits.json"
        if commits_file.exists():
            try:
                with open(commits_file, 'r') as f:
                    commits_data = json.load(f)
                    deleted_commit_count = len(commits_data.get("commits", []))
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        
        # Delete the objects directory and all its contents
        objects_dir = gitblend_dir / "objects"
        if objects_dir.exists():
            try:
                # Count files before deletion
                for uid_dir in objects_dir.iterdir():
                    if uid_dir.is_dir():
                        deleted_file_count += len(list(uid_dir.glob("*.blend")))
                
                # Remove the entire objects directory
                shutil.rmtree(objects_dir)
            except OSError as e:
                self.report({'ERROR'}, f"Failed to delete objects directory: {e}")
                return {'CANCELLED'}
        
        # Delete commits.json
        if commits_file.exists():
            try:
                commits_file.unlink()
            except OSError as e:
                self.report({'ERROR'}, f"Failed to delete commits.json: {e}")
                return {'CANCELLED'}
        
        # Delete staging directory if it exists
        staging_dir = gitblend_dir / "staging"
        if staging_dir.exists():
            try:
                shutil.rmtree(staging_dir)
            except OSError as e:
                self.report({'ERROR'}, f"Failed to delete staging directory: {e}")
                return {'CANCELLED'}
        
        # Clean up any preview objects in the scene (objects with UID suffixes)
        cleaned_objects = []
        for obj in list(bpy.context.scene.objects):
            if '_' in obj.name:
                suffix = obj.name.split('_')[-1]
                if len(suffix) == 8 and all(c in '0123456789abcdef' for c in suffix.lower()):
                    # This is a preview object with UID suffix
                    cleaned_objects.append(obj.name)
                    bpy.data.objects.remove(obj, do_unlink=True)
        
        # Clear the commit history UI
        scene.commit_history.clear()
        scene.i = 0
        
        # Comprehensive report
        message_parts = []
        if deleted_commit_count > 0:
            message_parts.append(f"{deleted_commit_count} commit(s)")
        if deleted_file_count > 0:
            message_parts.append(f"{deleted_file_count} object file(s)")
        if cleaned_objects:
            message_parts.append(f"{len(cleaned_objects)} preview object(s)")
        
        if message_parts:
            message = f"Purged: {', '.join(message_parts)}"
        else:
            message = "No commits found to purge"
        
        self.report({'INFO'}, message)
        return {'FINISHED'}