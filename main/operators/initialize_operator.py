"""
Refactored Initialize Operator for GitBlend - Uses service layer for clean separation of concerns.
"""

import bpy
from pathlib import Path
from ..core.repository_service import RepositoryService
from ..core.signature_service import SignatureService
from ..core.export_service import ExportService


class GITBLEND_OT_RefreshHistory(bpy.types.Operator):
    bl_idname = "gitblend.refresh_history"
    bl_label = "Refresh History"
    bl_description = "Refresh the commit history"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        populate_commit_history(context)
        self.report({'INFO'}, "Commit history refreshed")
        return {'FINISHED'}


class GITBLEND_OT_RefreshStatus(bpy.types.Operator):
    bl_idname = "gitblend.refresh_status"
    bl_label = "Refresh Status"
    bl_description = "Refresh the initialization status"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        check_and_update_initialized_property(context)
        return {'FINISHED'}


class GITBLEND_OT_Initialize(bpy.types.Operator):
    bl_idname = "gitblend.initialize"
    bl_label = "Initialize Git Blend"
    bl_description = "Initialize git blend repository for this .blend file"
    bl_options = {'REGISTER', 'UNDO'}
    
    commit_message: bpy.props.StringProperty(
        name="Initial Commit Message",
        description="Message for the initial commit",
        default="Initial commit"
    )
    
    @classmethod
    def poll(cls, context):
        # Can only initialize if blend file is saved
        return bpy.data.filepath != ""
    
    def execute(self, context):
        # Validate that operation can be performed
        if not bpy.data.filepath:
            self.report({'ERROR'}, "Blend file must be saved before initializing Git Blend")
            return {'CANCELLED'}
        
        # Initialize repository using service
        success, message, commit_data = RepositoryService.initialize_repository(self.commit_message)
        
        if not success:
            self.report({'ERROR'}, message)
            return {'CANCELLED'}
        
        try:
            # Generate initial signature
            initial_signature = SignatureService.generate_data_signature()
            
            # Save signature file
            RepositoryService.save_signature_file(commit_data['hash'], initial_signature)
            
            # Export initial data blocks
            project_dir, gitblend_dir = RepositoryService.get_project_paths()
            blend_export_path = gitblend_dir / f"{commit_data['hash']}.blend"
            
            if not ExportService.export_all_data_blocks(str(blend_export_path)):
                self.report({'ERROR'}, "Failed to export initial data blocks")
                return {'CANCELLED'}
            
            # Update initialized property
            context.scene.gitblend_props.initialized = True
            
            # Populate commit history
            populate_commit_history(context)
            
            self.report({'INFO'}, message)
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to initialize: {str(e)}")
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


# Utility functions for UI management
def check_and_update_initialized_property(context):
    """Check if gitblend is initialized and update the property accordingly."""
    is_initialized = RepositoryService.is_initialized()
    context.scene.gitblend_props.initialized = is_initialized
    return is_initialized


def check_initialized_status(context):
    """Read-only check of initialization status - safe to call from panel draw."""
    return RepositoryService.is_initialized()


def populate_commit_history(context):
    """Load commit history from metadata file into UI properties."""
    props = context.scene.gitblend_props
    props.commits.clear()
    
    # Get all commits from repository service
    commits_data = RepositoryService.get_all_commits()
    
    # Load commits in reverse order (newest first)
    for commit_data in reversed(commits_data):
        commit_entry = props.commits.add()
        commit_entry.hash = commit_data.get('hash', '')
        commit_entry.message = commit_data.get('message', '')
        commit_entry.timestamp = commit_data.get('timestamp', '')


def populate_ui_from_metadata(context):
    """Load commit history from metadata file into UI (legacy function)."""
    populate_commit_history(context)


def has_branches_from_commit(project_dir, commit_hash):
    """Check if commit has branches (placeholder for future implementation)."""
    return False


def update_branch_status(context):
    """Update branch status in UI (placeholder for future implementation)."""
    props = context.scene.gitblend_props
    props.current_branch_display = "main"
    props.is_on_head = True


def get_branch_names(project_dir):
    """Get list of branch names (placeholder for future implementation)."""
    return ["main"]


def populate_branch_commits(context):
    """Populate branch-specific commits (placeholder for future implementation)."""
    props = context.scene.gitblend_props
    # For now, just copy all commits to branch_commits
    props.branch_commits.clear()
    for commit in props.commits:
        branch_commit = props.branch_commits.add()
        branch_commit.hash = commit.hash
        branch_commit.message = commit.message
        branch_commit.timestamp = commit.timestamp


def should_show_commit_button_on_detached(context):
    """Check if commit button should be shown when detached (placeholder)."""
    return False


# Handler functions for automatic status updates
@bpy.app.handlers.persistent
def on_file_load_check_initialization(dummy):
    """Handler to check initialization status when a blend file is loaded."""
    try:
        context = bpy.context
        check_and_update_initialized_property(context)
        # Also populate commit history if initialized
        if context.scene.gitblend_props.initialized:
            populate_commit_history(context)
    except Exception:
        pass  # Silently fail if context is not available


@bpy.app.handlers.persistent
def on_file_save_check_initialization(dummy):
    """Handler to check initialization status when a blend file is saved."""
    try:
        context = bpy.context
        check_and_update_initialized_property(context)
        # Also populate commit history if initialized
        if context.scene.gitblend_props.initialized:
            populate_commit_history(context)
    except Exception:
        pass  # Silently fail if context is not available


def register_initialize():
    bpy.utils.register_class(GITBLEND_OT_RefreshHistory)
    bpy.utils.register_class(GITBLEND_OT_RefreshStatus)
    bpy.utils.register_class(GITBLEND_OT_Initialize)
    # Add handlers to check initialization status
    bpy.app.handlers.load_post.append(on_file_load_check_initialization)
    bpy.app.handlers.save_post.append(on_file_save_check_initialization)


def unregister_initialize():
    # Remove handlers
    if on_file_load_check_initialization in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_file_load_check_initialization)
    if on_file_save_check_initialization in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(on_file_save_check_initialization)
    bpy.utils.unregister_class(GITBLEND_OT_Initialize)
    bpy.utils.unregister_class(GITBLEND_OT_RefreshStatus)
    bpy.utils.unregister_class(GITBLEND_OT_RefreshHistory)