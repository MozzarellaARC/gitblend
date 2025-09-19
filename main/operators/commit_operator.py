"""
Refactored Commit Operator for GitBlend - Uses service layer for clean separation of concerns.
"""

import bpy
from datetime import datetime
from ..core.repository_service import RepositoryService
from ..core.signature_service import SignatureService
from ..core.export_service import ExportService
from ..core.change_detection import ChangeDetectionService


class GITBLEND_OT_Commit(bpy.types.Operator):
    bl_idname = "gitblend.commit"
    bl_label = "Commit Changes"
    bl_description = "Commit current changes to git blend repository"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        # Can only commit if blend file is saved and gitblend is initialized
        return RepositoryService.is_initialized()
    
    def execute(self, context):
        # Validate that operations can be performed
        can_operate, error_message = RepositoryService.validate_can_operate()
        if not can_operate:
            self.report({'ERROR'}, error_message)
            return {'CANCELLED'}
        
        try:
            # Get commit message from UI
            props = context.scene.gitblend_props
            commit_message = props.commit_message.strip()
            
            if not commit_message:
                self.report({'ERROR'}, "Commit message is required")
                return {'CANCELLED'}
            
            # Get parent commit hash (latest commit)
            parent_hash = RepositoryService.get_latest_commit_hash()
            
            # Detect changes before generating commit
            changes_detected, change_summary, changed_data_blocks = ChangeDetectionService.detect_changes_and_deltas(parent_hash)
            
            if not changes_detected:
                self.report({'INFO'}, "No changes detected - nothing to commit")
                return {'CANCELLED'}
            
            # Generate new commit data
            timestamp = datetime.now().isoformat()
            new_commit_hash = RepositoryService.generate_new_commit_hash(commit_message, parent_hash)
            
            # Get paths for export
            project_dir, gitblend_dir = RepositoryService.get_project_paths()
            final_blend_path = gitblend_dir / f"{new_commit_hash}.blend"
            
            # Export only the changed data blocks (delta export)
            export_success = ExportService.export_delta_data_blocks(str(final_blend_path), changed_data_blocks)
            if not export_success:
                self.report({'ERROR'}, "Failed to export data blocks")
                return {'CANCELLED'}
            
            # Generate and save signature file for this commit
            current_signature = SignatureService.generate_data_signature()
            RepositoryService.save_signature_file(new_commit_hash, current_signature)
            
            # Create new commit metadata
            changed_block_names = ChangeDetectionService.get_changed_block_names(changed_data_blocks)
            new_commit = {
                "hash": new_commit_hash,
                "timestamp": timestamp,
                "message": commit_message,
                "parent": parent_hash,
                "changes": change_summary,
                "delta_export": True,
                "changed_blocks": changed_block_names
            }
            
            # Add commit to metadata
            if not RepositoryService.add_commit_to_metadata(new_commit):
                self.report({'ERROR'}, "Failed to save commit metadata")
                return {'CANCELLED'}
            
            # Clean up temporary files
            RepositoryService.cleanup_temp_files()
            
            # Ensure initialized property is set to True
            props.initialized = True
            
            # Refresh UI
            from .initialize_operator import populate_ui_from_metadata
            populate_ui_from_metadata(context)
            
            # Report success with change summary
            changes_text = ChangeDetectionService.format_change_summary(change_summary)
            blocks_exported = len(changed_data_blocks)
            
            self.report({'INFO'}, f"Committed: {new_commit_hash[:8]} - {changes_text} ({blocks_exported} blocks exported)")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to commit: {str(e)}")
            return {'CANCELLED'}


def register_commit():
    bpy.utils.register_class(GITBLEND_OT_Commit)


def unregister_commit():
    bpy.utils.unregister_class(GITBLEND_OT_Commit)