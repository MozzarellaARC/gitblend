import bpy
import subprocess
import os
from pathlib import Path

class GITBLEND_OT_commit(bpy.types.Operator):
    bl_idname = "gb.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit changes to the Git repository"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gitblend_props
        commit_message = props.commit_message.strip()

        if not commit_message:
            self.report({'ERROR'}, "Commit message cannot be empty.")
            return {'CANCELLED'}

        # Get the current blend file path
        blend_filepath = bpy.data.filepath
        if not blend_filepath:
            self.report({'ERROR'}, "Please save the Blender file first.")
            return {'CANCELLED'}

        # Get the directory of the blend file
        blend_dir = os.path.dirname(blend_filepath)
        blend_filename = os.path.basename(blend_filepath)

        try:
            # Check if git is initialized
            git_check = subprocess.run(
                ["git.exe", "rev-parse", "--git-dir"],
                cwd=blend_dir,
                capture_output=True,
                text=True
            )
            
            # Initialize git if not already initialized
            if git_check.returncode != 0:
                self.report({'INFO'}, "Initializing Git repository...")
                init_result = subprocess.run(
                    ["git.exe", "init"],
                    cwd=blend_dir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                self.report({'INFO'}, "Git repository initialized.")

            # Check if git-lfs is installed
            lfs_check = subprocess.run(
                ["git-lfs.exe", "version"],
                capture_output=True,
                text=True
            )
            
            if lfs_check.returncode == 0:
                # Initialize LFS in the repository
                lfs_install = subprocess.run(
                    ["git-lfs.exe", "install"],
                    cwd=blend_dir,
                    capture_output=True,
                    text=True
                )
                
                # Track .blend files with LFS if not already tracked
                gitattributes_path = os.path.join(blend_dir, ".gitattributes")
                track_blend = True
                
                if os.path.exists(gitattributes_path):
                    with open(gitattributes_path, 'r') as f:
                        content = f.read()
                        if '*.blend' in content:
                            track_blend = False
                
                if track_blend:
                    track_result = subprocess.run(
                        ["git-lfs.exe", "track", "*.blend"],
                        cwd=blend_dir,
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    self.report({'INFO'}, "Configured Git LFS to track .blend files.")
                    
                    # Add .gitattributes to staging
                    subprocess.run(
                        ["git.exe", "add", ".gitattributes"],
                        cwd=blend_dir,
                        capture_output=True,
                        text=True
                    )
            else:
                self.report({'WARNING'}, "Git LFS not found. Proceeding without LFS support.")

            # Save the current blend file before committing
            bpy.ops.wm.save_mainfile()
            
            # Add the blend file to staging
            add_result = subprocess.run(
                ["git.exe", "add", blend_filename],
                cwd=blend_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Check if there are changes to commit
            status_result = subprocess.run(
                ["git.exe", "status", "--porcelain", blend_filename],
                cwd=blend_dir,
                capture_output=True,
                text=True
            )
            
            if not status_result.stdout.strip():
                self.report({'INFO'}, "No changes to commit.")
                return {'FINISHED'}
            
            # Commit the changes
            commit_result = subprocess.run(
                ["git.exe", "commit", "-m", commit_message],
                cwd=blend_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse commit output for information
            if commit_result.stdout:
                # Extract commit hash if available
                lines = commit_result.stdout.split('\n')
                for line in lines:
                    if 'commit' in line.lower():
                        self.report({'INFO'}, line.strip())
                        break
            
            self.report({'INFO'}, f"Successfully committed: {commit_message}")
            
            # Clear the commit message after successful commit
            props.commit_message = ""
            
            return {'FINISHED'}
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            self.report({'ERROR'}, f"Git operation failed: {error_msg}")
            return {'CANCELLED'}
        except FileNotFoundError as e:
            if "git.exe" in str(e):
                self.report({'ERROR'}, "git.exe not found. Please ensure Git is installed and in PATH.")
            elif "git-lfs.exe" in str(e):
                self.report({'WARNING'}, "git-lfs.exe not found. Continuing without LFS support.")
                # Try to proceed without LFS
                return self.execute_without_lfs(context, blend_dir, blend_filename, commit_message)
            else:
                self.report({'ERROR'}, f"File not found: {e}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {str(e)}")
            return {'CANCELLED'}

    def execute_without_lfs(self, context, blend_dir, blend_filename, commit_message):
        """Fallback method to commit without LFS"""
        try:
            # Save the file
            bpy.ops.wm.save_mainfile()
            
            # Add and commit
            subprocess.run(
                ["git.exe", "add", blend_filename],
                cwd=blend_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            subprocess.run(
                ["git.exe", "commit", "-m", commit_message],
                cwd=blend_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            self.report({'INFO'}, f"Committed without LFS: {commit_message}")
            context.scene.gitblend_props.commit_message = ""
            return {'FINISHED'}
            
        except subprocess.CalledProcessError as e:
            self.report({'ERROR'}, f"Git operation failed: {e.stderr if e.stderr else str(e)}")
            return {'CANCELLED'}


class GITBLEND_OT_refresh_commit_history(bpy.types.Operator):
    bl_idname = "gb.refresh_commit_history"
    bl_label = "Refresh Commit History"
    bl_description = "Reload commit history from the repository"
    bl_options = {'INTERNAL'}

    max_commits: bpy.props.IntProperty(  # type: ignore
        name="Max Commits",
        default=25,
        min=1,
        max=500,
    )

    def execute(self, context):
        props = context.scene.gitblend_props
        blend_filepath = bpy.data.filepath
        if not blend_filepath:
            self.report({'ERROR'}, "Please save the Blender file first.")
            return {'CANCELLED'}

        repo_dir = os.path.dirname(blend_filepath)

        # Clear existing collection
        props.commit_history.clear()

        # Run git log
        try:
            # --pretty format: hash%x1fauthor%x1fdate%x1fmessage%x1e (unit separator & record separator)
            format_str = "%H%x1f%an%x1f%ad%x1f%s%x1e"
            result = subprocess.run(
                ["git.exe", "log", f"--max-count={self.max_commits}", f"--pretty=format:{format_str}", "--date=short"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                self.report({'ERROR'}, f"git log failed: {result.stderr.strip()}")
                return {'CANCELLED'}

            records = result.stdout.strip().split("\x1e")
            for rec in records:
                if not rec.strip():
                    continue
                parts = rec.split("\x1f")
                if len(parts) != 4:
                    continue
                commit = props.commit_history.add()
                commit.hash, commit.author, commit.date, commit.message = parts

            return {'FINISHED'}
        except FileNotFoundError:
            self.report({'ERROR'}, "git.exe not found. Ensure Git is installed.")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {e}")
            return {'CANCELLED'}