"""
Refactored Checkout Operator for GitBlend - Uses service layer for clean separation of concerns.
"""

import bpy
from ..core.repository_service import RepositoryService
from ..core.signature_service import SignatureService
from ..core.export_service import ExportService


class GITBLEND_OT_Checkout(bpy.types.Operator):
    bl_idname = "gitblend.checkout"
    bl_label = "Checkout Commit"
    bl_description = "Checkout and restore scene to selected commit"
    bl_options = {'REGISTER', 'UNDO'}
    
    commit_hash: bpy.props.StringProperty(
        name="Commit Hash",
        description="Hash of commit to checkout"
    )
    
    @classmethod
    def poll(cls, context):
        # Can only checkout if blend file is saved and gitblend is initialized
        return RepositoryService.is_initialized()
    
    def execute(self, context):
        # Validate that operations can be performed
        can_operate, error_message = RepositoryService.validate_can_operate()
        if not can_operate:
            self.report({'ERROR'}, error_message)
            return {'CANCELLED'}
        
        # Debug: Print the commit hash we're looking for
        print(f"[GitBlend] Attempting to checkout commit: {self.commit_hash}")
        
        # Validate commit hash is provided
        if not self.commit_hash:
            self.report({'ERROR'}, "No commit hash provided. Please select a commit first.")
            return {'CANCELLED'}
        
        try:
            # Find target commit using repository service
            target_commit = RepositoryService.find_commit_by_hash(self.commit_hash)
            if not target_commit:
                print(f"[GitBlend] Commit hash '{self.commit_hash}' not found")
                self.report({'ERROR'}, f"Commit {self.commit_hash[:8]} not found")
                return {'CANCELLED'}
            
            # Build commit chain for delta reconstruction
            commit_chain = RepositoryService.build_commit_chain(self.commit_hash)
            if not commit_chain:
                self.report({'ERROR'}, "Failed to build commit chain")
                return {'CANCELLED'}
            
            # Load target commit signature to know what complete scene should look like
            target_signature = RepositoryService.load_signature_file(self.commit_hash)
            if not target_signature:
                self.report({'ERROR'}, "Could not load target commit signature")
                return {'CANCELLED'}
            
            # Use signature-based reconstruction
            print(f"[GitBlend] Reconstructing scene to match target signature")
            self._reconstruct_scene_from_signature(commit_chain, target_signature)
            
            # Simple cleanup of any remaining orphaned data blocks
            print(f"[GitBlend] Final cleanup of orphaned data blocks")
            self._cleanup_orphaned_data()
            
            # Update UI to show we're on this commit
            props = context.scene.gitblend_props
            props.current_commit = self.commit_hash
            
            # Refresh UI
            from .initialize_operator import populate_ui_from_metadata
            populate_ui_from_metadata(context)
            
            self.report({'INFO'}, f"Checked out commit {self.commit_hash[:8]}: {target_commit['message']}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to checkout: {str(e)}")
            return {'CANCELLED'}
    
    def _reconstruct_scene_from_signature(self, commit_chain, target_signature):
        """Reconstruct scene to match target signature by intelligently applying commits."""
        print(f"[GitBlend] Starting signature-based reconstruction")
        
        # Clear current scene first
        ExportService.clear_scene()
        
        # Step 1: Apply the initial commit (full state)
        initial_commit = commit_chain[0]
        initial_file_path = RepositoryService.get_commit_file_path(initial_commit['hash'])
        if initial_file_path:
            print(f"[GitBlend] Loading initial commit: {initial_commit['hash'][:8]}")
            ExportService.load_data_blocks_from_file(str(initial_file_path))
        
        # Step 2: Apply each delta commit
        for i, commit in enumerate(commit_chain[1:], 1):
            commit_file_path = RepositoryService.get_commit_file_path(commit['hash'])
            if not commit_file_path:
                continue
                
            is_delta = commit.get('delta_export', False)
            print(f"[GitBlend] Applying delta commit {i}/{len(commit_chain)-1}: {commit['hash'][:8]}")
            
            if is_delta:
                self._apply_delta_commit(str(commit_file_path))
            else:
                # If it's not a delta (shouldn't happen after initial), treat as full
                ExportService.load_data_blocks_from_file(str(commit_file_path))
        
        # Step 3: Ensure final scene matches target signature exactly
        self._enforce_signature_compliance(commit_chain, target_signature)
    
    def _enforce_signature_compliance(self, commit_chain, target_signature):
        """Ensure the final scene exactly matches what the target signature expects."""
        print(f"[GitBlend] Enforcing signature compliance")
        
        expected_objects = set(target_signature.get('objects', {}).keys())
        current_objects = set(obj.name for obj in bpy.data.objects)
        
        print(f"[GitBlend] Expected: {len(expected_objects)} objects")
        print(f"[GitBlend] Current: {len(current_objects)} objects")
        
        # Handle missing objects
        missing_objects = expected_objects - current_objects
        if missing_objects:
            print(f"[GitBlend] Missing {len(missing_objects)} objects: {missing_objects}")
            self._restore_missing_objects_from_chain(commit_chain, missing_objects)
        
        # Handle extra objects  
        extra_objects = current_objects - expected_objects
        if extra_objects:
            print(f"[GitBlend] Removing {len(extra_objects)} extra objects: {extra_objects}")
            self._remove_extra_objects(extra_objects)
        
        # Verify final state
        final_objects = set(obj.name for obj in bpy.data.objects)
        if final_objects == expected_objects:
            print(f"[GitBlend] ✓ Scene successfully reconstructed with {len(final_objects)} objects")
        else:
            missing_final = expected_objects - final_objects
            extra_final = final_objects - expected_objects
            print(f"[GitBlend] ⚠ Scene reconstruction incomplete:")
            if missing_final:
                print(f"[GitBlend]   Still missing: {missing_final}")
            if extra_final:
                print(f"[GitBlend]   Still extra: {extra_final}")
    
    def _restore_missing_objects_from_chain(self, commit_chain, missing_objects):
        """Try to restore missing objects by searching through all commits in the chain."""
        print(f"[GitBlend] Searching commit chain for {len(missing_objects)} missing objects")
        
        # Search commits in reverse order (newest first) to get latest versions
        for commit in reversed(commit_chain):
            if not missing_objects:  # All objects found
                break
                
            commit_file_path = RepositoryService.get_commit_file_path(commit['hash'])
            if not commit_file_path:
                continue
            
            try:
                # Check what objects are available in this commit
                with bpy.data.libraries.load(str(commit_file_path), link=False) as (data_from, data_to):
                    available_objects = set(data_from.objects)
                    objects_to_load = list(missing_objects & available_objects)
                    
                    if objects_to_load:
                        data_to.objects = objects_to_load
                        missing_objects -= set(objects_to_load)
                
                # Link found objects to scene
                scene = bpy.context.scene
                for obj in data_to.objects:
                    if obj and obj.name not in scene.objects:
                        scene.collection.objects.link(obj)
                        
            except Exception as e:
                print(f"[GitBlend] Error searching commit {commit['hash'][:8]}: {e}")
        
        if missing_objects:
            print(f"[GitBlend] Warning: Could not find {len(missing_objects)} objects in commit chain: {missing_objects}")
    
    def _apply_delta_commit(self, blend_file_path):
        """Apply delta commit by surgically replacing changed data blocks."""
        print(f"[GitBlend] Applying delta commit")
        
        try:
            # First, identify what data blocks are in this delta commit
            delta_data = {}
            
            with bpy.data.libraries.load(blend_file_path, link=False, assets_only=False) as (data_from, data_to):
                # Don't load anything yet, just inspect what's available
                for data_type in ['objects', 'meshes', 'materials', 'images', 'texts', 'actions', 'node_groups']:
                    if hasattr(data_from, data_type):
                        delta_data[data_type] = list(getattr(data_from, data_type))
            
            total_blocks = sum(len(blocks) for blocks in delta_data.values())
            print(f"[GitBlend] Delta contains {total_blocks} total data blocks")
            
            # Now surgically replace each type of data block
            # Process in dependency order: data blocks first, then objects that depend on them
            for data_type in ['node_groups', 'meshes', 'materials', 'images', 'texts', 'actions']:
                if delta_data.get(data_type):
                    ExportService.replace_data_blocks(blend_file_path, data_type, delta_data[data_type])
            
            # Process objects last, after their dependencies are in place
            if delta_data.get('objects'):
                ExportService.replace_objects(blend_file_path, delta_data['objects'])
                
        except Exception as e:
            print(f"[GitBlend] Error applying delta commit: {e}")
            raise
    
    def _remove_extra_objects(self, extra_objects):
        """Remove objects that shouldn't exist according to the target signature."""
        print(f"[GitBlend] Removing {len(extra_objects)} extra objects")
        
        scene = bpy.context.scene
        for obj_name in extra_objects:
            obj = bpy.data.objects.get(obj_name)
            if obj:
                try:
                    if obj.name in scene.objects:
                        scene.collection.objects.unlink(obj)
                    bpy.data.objects.remove(obj, do_unlink=True)
                except Exception as e:
                    print(f"[GitBlend] Error removing object {obj_name}: {e}")
    
    def _cleanup_orphaned_data(self):
        """Clean up orphaned data blocks after reconstruction."""
        print(f"[GitBlend] Cleaning up orphaned data blocks...")
        
        # Use the export service's cleanup logic
        data_collections = [
            ('meshes', bpy.data.meshes),
            ('materials', bpy.data.materials),
            ('images', bpy.data.images),
            ('actions', bpy.data.actions),
            ('node_groups', bpy.data.node_groups),
            ('texts', bpy.data.texts)
        ]
        
        total_removed = 0
        for collection_name, collection in data_collections:
            removed_count = 0
            for item in list(collection):
                if item.users == 0 and not getattr(item, 'use_fake_user', False):
                    collection.remove(item, do_unlink=True)
                    removed_count += 1
            total_removed += removed_count
            
            if removed_count > 0:
                print(f"[GitBlend] Removed {removed_count} orphaned {collection_name}")
        
        print(f"[GitBlend] Cleanup complete: removed {total_removed} total orphaned data blocks")


def register_checkout():
    bpy.utils.register_class(GITBLEND_OT_Checkout)


def unregister_checkout():
    bpy.utils.unregister_class(GITBLEND_OT_Checkout)