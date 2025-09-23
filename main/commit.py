from os import mkdir
import bpy
from pathlib import Path
import time
import uuid
import json
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
        gitblend_dir.mkdir(exist_ok=True)

        # Check for existing commits that need to be synchronized
        # Check if commits.json exists and has commits
        commits_file = gitblend_dir / "commits.json"
        has_existing_commits = commits_file.exists()
        if has_existing_commits:
            try:
                with open(commits_file, 'r') as f:
                    commits_data = json.load(f)
                    has_existing_commits = len(commits_data.get("commits", [])) > 0
            except (json.JSONDecodeError, FileNotFoundError):
                has_existing_commits = False
        
        has_loaded_history = len(scene.commit_history) > 0

        # If there are existing commit files but no loaded history, sync first
        if has_existing_commits and not has_loaded_history:
            self.report({'WARNING'}, "Found existing commits. Synchronizing...")
            refresh_commit_history(context)
            return {'CANCELLED'}

        # Check if staging directory exists and has files
        staging_dir = gitblend_dir / "staging"
        if not staging_dir.exists() or not any(staging_dir.iterdir()):
            # If this is the first commit (no existing commits), trigger staging manually
            if not has_existing_commits:
                self.report({'INFO'}, "First commit: Staging current scene...")
                # Manually trigger staging for initialization
                from .stage import stage_obj_handler
                stage_obj_handler(None, context)
                
                # Check again if staging worked
                if not staging_dir.exists() or not any(staging_dir.iterdir()):
                    self.report({'ERROR'}, "Failed to stage files for first commit.")
                    return {'CANCELLED'}
            else:
                self.report({'WARNING'}, "No staged changes found. Save the file to stage changes.")
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
            # Update the commits.json file
            commits_file = gitblend_dir / "commits.json"
            timestamp = time.strftime("%d-%m-%y")
            
            # Load existing commits or create new structure
            if commits_file.exists():
                with open(commits_file, 'r') as f:
                    commits_data = json.load(f)
            else:
                commits_data = {"commits": []}
            
            # Add new commit record
            new_commit = {
                "uid": commit_uid,
                "timestamp": timestamp,
                "files": len(moved_files),
                "file_list": moved_files,
                "created_at": time.time()  # For sorting
            }
            
            commits_data["commits"].append(new_commit)
            
            # Save updated commits.json
            with open(commits_file, 'w') as f:
                json.dump(commits_data, f, indent=2)
            
            self.report({'INFO'}, f"Committed {len(moved_files)} file(s) to objects/{commit_uid}")
        else:
            self.report({'WARNING'}, "No files to commit from staging directory.")

        # Refresh commit history to show the new commit
        refresh_commit_history(context)
        return {'FINISHED'}

        
        
        