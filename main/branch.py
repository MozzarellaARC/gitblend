import bpy
import hashlib
import time
from pathlib import Path
from typing import Any, Dict

# Use shared initialization + metadata utilities
from .initialize import (
    ensure_gitblend_dir, append_commit, is_gitblend_initialized, 
    is_ui_synced_with_metadata, is_on_head_commit, get_current_commit_hash,
    create_branch, populate_ui_from_metadata
)

"""
BRANCH ARCHITECTURE - OPERATION ORDER

The branch system extends the existing commit architecture with the following concepts:

1. BRANCH METADATA STRUCTURE:
   - branches: dict mapping branch_name -> {head_commit, created_from, created_at}
   - current_branch: string indicating which branch is currently active
   - head_commit: hash of the latest commit on the current branch

2. HEAD vs DETACHED STATE:
   - HEAD: User is on the latest commit of the current branch
   - DETACHED: User has checked out an older commit (not the branch head)

3. BRANCH CREATION FLOW:
   - Only available when user is in DETACHED state (not on HEAD)
   - Creates new branch starting from the current commit
   - Uses the current commit's message as the branch name
   - Switches to the new branch automatically

4. BRANCH CREATION PROCESS:
   - Validate user is in detached state
   - Get current commit hash and message
   - Create branch metadata entry
   - No new snapshot needed (branch points to existing commit)
   - Update current_branch in metadata
   - Refresh UI to show new branch state

5. UI INTEGRATION:
   - Show current branch and HEAD status
   - Replace "Commit" button with "Create Branch" button when detached
   - Provide branch selection dropdown
   - Display whether user is on HEAD or detached state
"""


def _compute_scene_hash(scene: bpy.types.Scene) -> str:
    """Compute a sha-256 hash representing the current scene state.
    For now we use a combination of object names, modification times and a timestamp
    to ensure uniqueness. This can evolve into a deterministic content hash later.
    """
    h = hashlib.sha256()
    # Basic entropy: object names and counts
    try:
        for obj in scene.objects:
            h.update(obj.name.encode('utf-8', 'ignore'))
            h.update(str(obj.type).encode())
    except Exception:
        pass
    # Add current time to guarantee uniqueness even if scene unchanged
    h.update(str(time.time_ns()).encode())
    return h.hexdigest()


class GITBLEND_OT_create_branch(bpy.types.Operator):
    bl_idname = "gitblend.create_branch"
    bl_label = "Create Branch"
    bl_description = "Create a new branch from the current commit (only available when not on HEAD)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):  # type: ignore
        # Must have saved blend file and initialization present
        blend_path = bpy.data.filepath
        if not blend_path:
            return False
        try:
            from pathlib import Path as _P
            project_dir = _P(blend_path).resolve().parent
            if not is_gitblend_initialized(project_dir):
                return False
            # Must be synced with metadata
            if not is_ui_synced_with_metadata(context):
                return False
            # Must NOT be on HEAD commit (detached state required)
            return not is_on_head_commit(context)
        except Exception:
            return False

    def execute(self, context):
        # Set branch operation flag to prevent interference
        wm = context.window_manager
        if wm.get('gitblend_branch_in_progress'):
            self.report({'WARNING'}, "Branch operation already in progress")
            return {'CANCELLED'}
        
        wm['gitblend_branch_in_progress'] = True
        
        try:
            # Determine current working .blend file path
            current_filepath = bpy.data.filepath
            if not current_filepath:
                self.report({'ERROR'}, "Please save the .blend file before creating a branch.")
                return {'CANCELLED'}

            current_dir = Path(current_filepath).resolve().parent
            
            # Check if .gitblend is initialized
            if not is_gitblend_initialized(current_dir):
                self.report({'ERROR'}, "Repository not initialized. Please initialize first.")
                return {'CANCELLED'}
            
            # Check if UI is synced with metadata
            if not is_ui_synced_with_metadata(context):
                self.report({'ERROR'}, "Commit history not synchronized. Please sync first.")
                return {'CANCELLED'}
            
            # Verify user is in detached state (not on HEAD)
            if is_on_head_commit(context):
                self.report({'ERROR'}, "Cannot create branch: you are on HEAD commit. Please checkout an older commit first.")
                return {'CANCELLED'}
            
            # Get current commit info
            current_commit_hash = get_current_commit_hash(context)
            if not current_commit_hash:
                self.report({'ERROR'}, "No current commit found.")
                return {'CANCELLED'}
            
            # Get current commit message to use as branch name
            props = getattr(context.scene, "gitblend_props", None)
            if not props or props.commits_index < 0 or props.commits_index >= len(props.commits):
                self.report({'ERROR'}, "Invalid commit selection.")
                return {'CANCELLED'}
            
            current_commit = props.commits[props.commits_index]
            branch_name = current_commit.message.strip()
            
            if not branch_name:
                self.report({'ERROR'}, "Cannot create branch: commit message is empty.")
                return {'CANCELLED'}
            
            # Sanitize branch name (remove problematic characters)
            import re
            branch_name = re.sub(r'[^\w\s-]', '', branch_name)[:50]  # Limit length
            branch_name = re.sub(r'\s+', '_', branch_name)  # Replace spaces with underscores
            
            if not branch_name:
                self.report({'ERROR'}, "Cannot create branch: commit message contains no valid characters.")
                return {'CANCELLED'}
            
            # Check if branch name already exists
            try:
                from .initialize import get_branch_names
                existing_branches = get_branch_names(current_dir)
                if branch_name in existing_branches:
                    self.report({'ERROR'}, f"Branch '{branch_name}' already exists.")
                    return {'CANCELLED'}
            except Exception as e:
                self.report({'ERROR'}, f"Failed to check existing branches: {e}")
                return {'CANCELLED'}
            
            # Create the branch
            try:
                create_branch(current_dir, branch_name, current_commit_hash)
            except Exception as e:
                self.report({'ERROR'}, f"Failed to create branch: {e}")
                return {'CANCELLED'}
            
            # Refresh UI to show updated branch state
            try:
                populate_ui_from_metadata(context)
            except Exception as e:
                self.report({'WARNING'}, f"Branch created but UI refresh failed: {e}")
            
            # Force UI redraw
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

            self.report({'INFO'}, f"Created branch '{branch_name}' from commit {current_commit_hash[:8]}")
            return {'FINISHED'}
        
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error during branch creation: {e}")
            return {'CANCELLED'}
        
        finally:
            # Always clean up the branch flag
            if 'gitblend_branch_in_progress' in wm:
                del wm['gitblend_branch_in_progress']


class GITBLEND_OT_switch_branch(bpy.types.Operator):
    bl_idname = "gitblend.switch_branch"
    bl_label = "Switch Branch"
    bl_description = "Switch to the selected branch"
    bl_options = {'REGISTER', 'UNDO'}

    branch_name: bpy.props.StringProperty(name="Branch Name")  # type: ignore

    @classmethod
    def poll(cls, context):  # type: ignore
        blend_path = bpy.data.filepath
        if not blend_path:
            return False
        try:
            from pathlib import Path as _P
            project_dir = _P(blend_path).resolve().parent
            return is_gitblend_initialized(project_dir)
        except Exception:
            return False

    def execute(self, context):
        if not self.branch_name:
            self.report({'ERROR'}, "No branch name specified")
            return {'CANCELLED'}
        
        current_filepath = bpy.data.filepath
        if not current_filepath:
            self.report({'ERROR'}, "Please save the .blend file first.")
            return {'CANCELLED'}

        current_dir = Path(current_filepath).resolve().parent
        
        try:
            # Load metadata and switch to branch
            from .initialize import load_metadata, write_metadata_atomic
            metadata = load_metadata(current_dir)
            
            if self.branch_name not in metadata.get('branches', {}):
                self.report({'ERROR'}, f"Branch '{self.branch_name}' does not exist.")
                return {'CANCELLED'}
            
            # Update current branch
            metadata['current_branch'] = self.branch_name
            
            # Get the head commit of the target branch
            branch_info = metadata['branches'][self.branch_name]
            head_commit = branch_info.get('head_commit')
            
            if head_commit:
                # Find the commit index and switch to it
                props = getattr(context.scene, "gitblend_props", None)
                if props:
                    for i, commit in enumerate(props.commits):
                        if commit.hash == head_commit:
                            # Set commit index (this will trigger auto-checkout)
                            props.commits_index = i
                            break
            
            # Update metadata
            write_metadata_atomic(current_dir, metadata)
            
            # Update UI status
            try:
                from .initialize import update_branch_status
                update_branch_status(context)
            except Exception:
                pass
            
            self.report({'INFO'}, f"Switched to branch '{self.branch_name}'")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to switch branch: {e}")
            return {'CANCELLED'}


__all__ = ["GITBLEND_OT_create_branch", "GITBLEND_OT_switch_branch"]