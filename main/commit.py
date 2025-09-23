from os import mkdir
import bpy
from pathlib import Path
import time
import uuid
from .refresh import refresh_commit_history

class GITBLEND_OT_Commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit current changes to .gitblend repository"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene.gitblend_props

        # Ensure save
        if not bpy.data.filepath:
            self.report({'ERROR'}, "Please save the current Blender file before committing.")
            return {'CANCELLED'}

        # Ensure .gitblend directory exists
        gitblend_dir = Path(bpy.data.filepath).parent / ".gitblend"
        if not gitblend_dir.exists():
            mkdir(gitblend_dir)

        # If .gitblend exists and there are commits, proceed to sync
        if gitblend_dir.exists() and any(gitblend_dir.iterdir()) and not scene.commit_history.items():
            self.report({'WARNING'}, ".gitblend commit history exists proceed to synchronize.")
            refresh_commit_history(context)
            return {'CANCELLED'}

        # Check if staging directory exists and has files
        staging_dir = gitblend_dir / "staging"
        if not staging_dir.exists() or not any(staging_dir.iterdir()):
            self.report({'WARNING'}, "No staged files found. Save the file to stage changes.")
            return {'CANCELLED'}

        # Create objects directory if it doesn't exist
        objects_dir = gitblend_dir / "objects"
        objects_dir.mkdir(exist_ok=True)

        # Generate unique UID for this commit
        commit_uid = str(uuid.uuid4())[:8]  # Use first 8 characters of UUID
        commit_objects_dir = objects_dir / commit_uid
        commit_objects_dir.mkdir(exist_ok=True)

        # Move all files from staging to objects/uid directory
        moved_files = []
        for file_path in staging_dir.iterdir():
            if file_path.is_file():
                dest_path = commit_objects_dir / file_path.name
                file_path.rename(dest_path)
                moved_files.append(file_path.name)

        if moved_files:
            self.report({'INFO'}, f"Committed {len(moved_files)} file(s) to objects/{commit_uid}")
        else:
            self.report({'WARNING'}, "No files to commit from staging directory.")

        # Refresh commit history to show the new commit
        refresh_commit_history(context)
        return {'FINISHED'}

        
        
        