import bpy  # type: ignore
import json
from pathlib import Path
from typing import Dict, List, Any, Set
from .utils import (
    get_gitblend_dir,
    load_commit_metadata,
    save_commit_metadata,
    resolve_commit_hash,
    validate_tree_hash,
    clear_scene_data,
    import_data_blocks_from_blend,
    serialize_data_blocks,
    generate_tree_hash
)


class GITBLEND_OT_Checkout(bpy.types.Operator):
    """Checkout a specific commit."""
    bl_idname = "gitblend.checkout"
    bl_label = "Checkout Commit"
    bl_description = "Checkout a specific commit and restore data blocks"
    bl_options = {'REGISTER', 'UNDO'}
    
    commit_hash: bpy.props.StringProperty(
        name="Commit Hash",
        description="Hash of the commit to checkout (full or partial hash, or 'HEAD')",
        default="HEAD"
    )
    
    def execute(self, context):
        try:
            # Check if git_blend is initialized
            gitblend_dir = get_gitblend_dir()
            if not gitblend_dir.exists():
                self.report({'ERROR'}, "Git Blend not initialized. Please initialize first.")
                return {'CANCELLED'}
            
            # Load commit metadata
            metadata = load_commit_metadata(gitblend_dir)
            
            if not metadata.get("commits"):
                self.report({'ERROR'}, "No commits found in repository.")
                return {'CANCELLED'}
            
            # Resolve the commit hash
            target_commit_hash = resolve_commit_hash(metadata, self.commit_hash)
            
            if not target_commit_hash:
                self.report({'ERROR'}, f"Commit '{self.commit_hash}' not found.")
                return {'CANCELLED'}
            
            if target_commit_hash not in metadata["commits"]:
                self.report({'ERROR'}, f"Commit '{target_commit_hash}' not found in metadata.")
                return {'CANCELLED'}
            
            # Get commit data
            commit_data = metadata["commits"][target_commit_hash]
            
            # Extract git-like commit information
            commit_hash = commit_data.get("commit", target_commit_hash)
            tree_hash = commit_data.get("tree")
            parent_hash = commit_data.get("parent")
            timestamp = commit_data.get("timestamp")
            message = commit_data.get("message", "No message")
            
            self.report({'INFO'}, f"Checking out commit: {commit_hash[:8]} - {message}")
            
            # Clear current scene data for clean checkout
            self.report({'INFO'}, "Clearing current scene data...")
            clear_scene_data()
            
            # Import data blocks from commit's blend file
            blend_filename = commit_data.get("blend_file")
            if blend_filename:
                blend_filepath = gitblend_dir / blend_filename
                if blend_filepath.exists():
                    self.report({'INFO'}, f"Importing data blocks from {blend_filename}...")
                    success = import_data_blocks_from_blend(blend_filepath)
                    if not success:
                        self.report({'WARNING'}, "Failed to import some data blocks from blend file")
                else:
                    self.report({'WARNING'}, f"Blend file {blend_filename} not found, skipping import")
            
            # Validate the tree hash if available
            if tree_hash:
                self.report({'INFO'}, "Validating reconstructed state...")
                
                # Serialize current data state
                current_data = {
                    "objects": list(bpy.data.objects),
                    "meshes": list(bpy.data.meshes),
                    "materials": list(bpy.data.materials),
                    "images": list(bpy.data.images),
                    "texts": list(bpy.data.texts),
                    "actions": list(bpy.data.actions),
                    "node_groups": list(bpy.data.node_groups)
                }
                serialized_current = serialize_data_blocks(current_data)
                
                # Validate against the tree hash
                if validate_tree_hash(serialized_current, tree_hash):
                    self.report({'INFO'}, "✓ Tree hash validation successful")
                else:
                    # Compare with stored data blocks to see if we can reconstruct
                    stored_data_blocks = commit_data.get("data_blocks", {})
                    if validate_tree_hash(stored_data_blocks, tree_hash):
                        self.report({'WARNING'}, "⚠ Current state doesn't match tree hash, but stored data is valid")
                        # TODO: Could implement more sophisticated reconstruction here
                    else:
                        self.report({'ERROR'}, "✗ Tree hash validation failed - data may be corrupted")
            
            # Update current commit in metadata
            metadata["current_commit"] = target_commit_hash
            save_commit_metadata(gitblend_dir, metadata)
            
            # Display commit information
            if parent_hash:
                self.report({'INFO'}, f"Parent: {parent_hash[:8]}")
            if tree_hash:
                self.report({'INFO'}, f"Tree: {tree_hash[:8]}")
            
            # Refresh any UI that shows current commit
            if hasattr(bpy.ops, 'gitblend') and hasattr(bpy.ops.gitblend, 'refresh_commits'):
                bpy.ops.gitblend.refresh_commits()
            
            self.report({'INFO'}, f"Successfully checked out commit {commit_hash[:8]}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to checkout commit: {str(e)}")
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        # Get the selected commit from the UI if available
        if hasattr(context.scene, 'gitblend') and hasattr(context.scene.gitblend, 'commits'):
            commits = context.scene.gitblend.commits
            active_index = context.scene.gitblend.active_commit_index
            if 0 <= active_index < len(commits):
                selected_commit = commits[active_index]
                self.commit_hash = getattr(selected_commit, 'hash', 'HEAD')
        
        return context.window_manager.invoke_props_dialog(self)