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
            # Get gitblend directory
            gitblend_dir = get_gitblend_dir()
            if not gitblend_dir.exists():
                self.report({'ERROR'}, "Repository not initialized. Please initialize first.")
                return {'CANCELLED'}
            
            # Load commit metadata
            metadata = load_commit_metadata(gitblend_dir)
            if not metadata.get("commits"):
                self.report({'ERROR'}, "No commits found in repository")
                return {'CANCELLED'}
            
            # Resolve commit hash
            target_commit_hash = resolve_commit_hash(metadata, self.commit_hash)
            if not target_commit_hash:
                self.report({'ERROR'}, f"Commit '{self.commit_hash}' not found")
                return {'CANCELLED'}
            
            # Get target commit info
            target_commit = metadata["commits"].get(target_commit_hash)
            if not target_commit:
                self.report({'ERROR'}, f"Commit data for '{target_commit_hash[:8]}' not found")
                return {'CANCELLED'}
            
            # Build commit chain from initial to target
            commit_chain = self._build_commit_chain(metadata, target_commit_hash)
            if not commit_chain:
                self.report({'ERROR'}, "Failed to build commit chain")
                return {'CANCELLED'}
            
            # Clear existing scene data
            self.report({'INFO'}, "Clearing current scene...")
            clear_scene_data()
            
            # Reconstruct data blocks from commit chain
            reconstructed_blocks = {}
            for commit_hash in commit_chain:
                commit = metadata["commits"][commit_hash]
                self.report({'INFO'}, f"Applying commit {commit_hash[:8]}...")
                
                # Load the JSON file for this commit
                json_file = gitblend_dir / f"{commit['tree_hash']}.json"
                if json_file.exists():
                    with open(json_file, 'r') as f:
                        commit_data = json.load(f)
                    
                    # Track which blocks are modified, new, or deleted
                    self._update_reconstructed_blocks(reconstructed_blocks, commit_data)
                    
                    # Import the .blend file for this commit
                    blend_file = gitblend_dir / f"{commit['tree_hash']}.blend"
                    if blend_file.exists():
                        success = import_data_blocks_from_blend(blend_file)
                        if not success:
                            self.report({'WARNING'}, f"Failed to import some data from commit {commit_hash[:8]}")
            
            # Validate the reconstruction (optional)
            if "tree_hash" in target_commit:
                current_state = self._get_current_scene_state()
                serialized = serialize_data_blocks(current_state)
                if not validate_tree_hash(serialized, target_commit["tree_hash"]):
                    self.report({'WARNING'}, "Tree hash mismatch after checkout. Data may be inconsistent.")
            
            # Update current commit pointer
            metadata["current_commit"] = target_commit_hash
            save_commit_metadata(gitblend_dir, metadata)
            
            self.report({'INFO'}, f"Successfully checked out commit {target_commit_hash[:8]}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Checkout failed: {str(e)}")
            return {'CANCELLED'}
    
    def _build_commit_chain(self, metadata: Dict[str, Any], target_hash: str) -> List[str]:
        """Build the chain of commits from initial to target."""
        chain = []
        current_hash = target_hash
        
        # Follow parent links back to initial commit
        while current_hash:
            chain.append(current_hash)
            commit = metadata["commits"].get(current_hash)
            if not commit:
                break
            current_hash = commit.get("parent")
        
        # Reverse to get chronological order (initial -> target)
        chain.reverse()
        return chain
    
    def _update_reconstructed_blocks(self, reconstructed: Dict, commit_data: Dict) -> None:
        """Update the reconstructed blocks dictionary with commit data."""
        for category, blocks in commit_data.items():
            if category == "commit_info":
                continue
                
            if category not in reconstructed:
                reconstructed[category] = {}
            
            for block in blocks:
                block_name = block.get("name")
                if block_name:
                    # Check status flags
                    if block.get("deleted"):
                        # Mark as deleted
                        if block_name in reconstructed[category]:
                            del reconstructed[category][block_name]
                    elif block.get("modified") or block.get("new"):
                        # Add or update the block
                        reconstructed[category][block_name] = block
    
    def _get_current_scene_state(self) -> Dict[str, List]:
        """Get the current state of all data blocks in the scene."""
        return {
            "objects": list(bpy.data.objects),
            "meshes": list(bpy.data.meshes),
            "materials": list(bpy.data.materials),
            "images": list(bpy.data.images),
            "texts": list(bpy.data.texts),
            "actions": list(bpy.data.actions),
            "node_groups": list(bpy.data.node_groups)
        }
    
    def invoke(self, context, event):
        """Show dialog to input commit hash."""
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        """Draw the operator dialog."""
        layout = self.layout
        layout.prop(self, "commit_hash")
        
        # Show recent commits for reference
        try:
            gitblend_dir = get_gitblend_dir()
            if gitblend_dir.exists():
                metadata = load_commit_metadata(gitblend_dir)
                if metadata.get("commits"):
                    box = layout.box()
                    box.label(text="Recent commits:")
                    
                    # Show last 5 commits
                    commits = list(metadata["commits"].items())
                    for i, (hash, commit) in enumerate(commits[-5:]):
                        row = box.row()
                        is_current = hash == metadata.get("current_commit")
                        prefix = "* " if is_current else "  "
                        row.label(text=f"{prefix}{hash[:8]}: {commit.get('message', 'No message')}")
                        if i >= 4:
                            break
        except:
            pass