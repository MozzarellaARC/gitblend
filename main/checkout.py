import bpy  # type: ignore
import json
from pathlib import Path


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
        if not bpy.data.filepath:
            return False
        
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        gitblend_dir = project_dir / ".gitblend"
        
        return gitblend_dir.exists()
    
    def execute(self, context):
        blend_path = Path(bpy.data.filepath).resolve()
        project_dir = blend_path.parent
        gitblend_dir = project_dir / ".gitblend"
        metadata_file = gitblend_dir / "commits.json"
        
        # Debug: Print the commit hash we're looking for
        print(f"[GitBlend] Attempting to checkout commit: {self.commit_hash}")
        
        # Validate commit hash is provided
        if not self.commit_hash:
            self.report({'ERROR'}, "No commit hash provided. Please select a commit first.")
            return {'CANCELLED'}
        
        # Validate .gitblend exists
        if not gitblend_dir.exists():
            self.report({'ERROR'}, "Git Blend not initialized")
            return {'CANCELLED'}
        
        # Load metadata
        if not metadata_file.exists():
            self.report({'ERROR'}, "No commits found")
            return {'CANCELLED'}
        
        try:
            with metadata_file.open('r') as f:
                metadata = json.load(f)
            
            commits = metadata.get('commits', [])
            if not commits:
                self.report({'ERROR'}, "No commits found in metadata")
                return {'CANCELLED'}
            
            # Debug: Print available commits
            print(f"[GitBlend] Available commits:")
            for commit in commits:
                print(f"  - {commit.get('hash', 'NO_HASH')[:8]}: {commit.get('message', 'NO_MESSAGE')}")
            
            # Find target commit
            target_commit = None
            for commit in commits:
                if commit['hash'] == self.commit_hash:
                    target_commit = commit
                    break
            
            if not target_commit:
                print(f"[GitBlend] Commit hash '{self.commit_hash}' not found in available commits")
                self.report({'ERROR'}, f"Commit {self.commit_hash[:8]} not found")
                return {'CANCELLED'}
            
            # Build commit chain for delta reconstruction
            commit_chain = self._build_commit_chain(commits, target_commit)
            
            if not commit_chain:
                self.report({'ERROR'}, "Failed to build commit chain")
                return {'CANCELLED'}
            
            # Clear current scene
            self._clear_scene()
            
            # Apply commits in order (delta reconstruction)
            for commit in commit_chain:
                commit_file = gitblend_dir / f"{commit['hash']}.blend"
                
                if not commit_file.exists():
                    self.report({'ERROR'}, f"Commit file {commit['hash'][:8]} not found")
                    return {'CANCELLED'}
                
                # Load and apply this commit's data
                self._apply_commit_data(str(commit_file), commit.get('delta_export', False))
            
            # Update UI to show we're on this commit
            props = context.scene.gitblend_props
            props.current_commit = self.commit_hash
            
            # Refresh UI
            from .initialize import populate_ui_from_metadata
            populate_ui_from_metadata(context)
            
            self.report({'INFO'}, f"Checked out commit {self.commit_hash[:8]}: {target_commit['message']}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to checkout: {str(e)}")
            return {'CANCELLED'}
    
    def _build_commit_chain(self, all_commits, target_commit):
        """Build the chain of commits from initial to target for delta reconstruction"""
        chain = []
        current = target_commit
        
        # Create a lookup map for faster parent finding
        commit_map = {commit['hash']: commit for commit in all_commits}
        
        # Build chain backwards from target to initial
        while current:
            chain.append(current)
            
            # Find parent
            parent_hash = current.get('parent')
            if parent_hash and parent_hash in commit_map:
                current = commit_map[parent_hash]
            else:
                # Reached initial commit or broken chain
                break
        
        # Reverse to get chronological order (initial -> target)
        chain.reverse()
        
        return chain
    
    def _clear_scene(self):
        """Clear all data blocks from the current scene"""
        # Store viewport settings before clearing
        viewport_settings = self._store_viewport_settings()
        
        # Clear in reverse dependency order to avoid issues
        # First clear objects (they reference other data)
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        
        # Clear orphaned meshes
        for mesh in list(bpy.data.meshes):
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh, do_unlink=True)
        
        # Clear orphaned materials
        for mat in list(bpy.data.materials):
            if mat.users == 0:
                bpy.data.materials.remove(mat, do_unlink=True)
        
        # Clear orphaned images
        for img in list(bpy.data.images):
            if img.users == 0:
                bpy.data.images.remove(img, do_unlink=True)
        
        # Clear orphaned actions
        for action in list(bpy.data.actions):
            if action.users == 0:
                bpy.data.actions.remove(action, do_unlink=True)
        
        # Clear texts (usually safe to clear all)
        for text in list(bpy.data.texts):
            if text.users == 0:
                bpy.data.texts.remove(text, do_unlink=True)
        
        # Restore viewport settings
        self._restore_viewport_settings(viewport_settings)
    
    def _store_viewport_settings(self):
        """Store current viewport settings to restore after clearing"""
        settings = {}
        
        # Store 3D viewport settings if available
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces[0]
                settings['viewport'] = {
                    'view_location': space.region_3d.view_location.copy() if hasattr(space, 'region_3d') else None,
                    'view_rotation': space.region_3d.view_rotation.copy() if hasattr(space, 'region_3d') else None,
                    'view_distance': space.region_3d.view_distance if hasattr(space, 'region_3d') else None,
                }
                break
        
        return settings
    
    def _restore_viewport_settings(self, settings):
        """Restore viewport settings after clearing"""
        if 'viewport' not in settings:
            return
        
        viewport_settings = settings['viewport']
        
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces[0]
                if hasattr(space, 'region_3d'):
                    region_3d = space.region_3d
                    if viewport_settings['view_location']:
                        region_3d.view_location = viewport_settings['view_location']
                    if viewport_settings['view_rotation']:
                        region_3d.view_rotation = viewport_settings['view_rotation']
                    if viewport_settings['view_distance']:
                        region_3d.view_distance = viewport_settings['view_distance']
                break
    
    def _apply_commit_data(self, blend_file_path, is_delta=False):
        """Apply data from a commit file (handles both full and delta exports)"""
        # Use append to merge data from the commit file
        with bpy.data.libraries.load(blend_file_path, link=False) as (data_from, data_to):
            # Load all data blocks specified in data.instructions.md
            
            # Objects - these pull in their dependencies automatically
            data_to.objects = data_from.objects
            
            # For delta commits, we want to replace existing data blocks with same names
            if is_delta:
                # Track what we're importing to handle replacements
                imported_objects = set(data_from.objects)
                imported_meshes = set(data_from.meshes)
                imported_materials = set(data_from.materials)
                imported_images = set(data_from.images)
                imported_texts = set(data_from.texts)
                imported_actions = set(data_from.actions)
                
                # Load all data types for delta reconstruction
                data_to.meshes = data_from.meshes
                data_to.materials = data_from.materials
                data_to.images = data_from.images
                data_to.texts = data_from.texts
                data_to.actions = data_from.actions
            else:
                # For full exports, load everything
                data_to.meshes = data_from.meshes
                data_to.materials = data_from.materials
                data_to.images = data_from.images
                data_to.texts = data_from.texts
                data_to.actions = data_from.actions
        
        # Link loaded objects to the scene
        scene = bpy.context.scene
        for obj in data_to.objects:
            if obj and obj.name not in scene.objects:
                scene.collection.objects.link(obj)
        
        # Handle replacements for delta commits
        if is_delta:
            self._handle_delta_replacements(data_to)
    
    def _handle_delta_replacements(self, imported_data):
        """Handle replacements of existing data blocks for delta reconstruction"""
        # For delta commits, newer versions should replace older ones
        # This is handled by Blender's append system which renames duplicates
        # We need to clean up the renamed versions and keep the latest
        
        # Process objects
        for obj in imported_data.objects:
            if not obj:
                continue
            
            # Check if this is a replacement (has .001 suffix or similar)
            base_name = obj.name.rsplit('.', 1)[0]
            
            # Find and remove older version if it exists
            old_obj = bpy.data.objects.get(base_name)
            if old_obj and old_obj != obj:
                # Replace old object with new one in scene
                for scene in bpy.data.scenes:
                    if old_obj.name in scene.objects:
                        scene.collection.objects.unlink(old_obj)
                
                # Remove old object
                bpy.data.objects.remove(old_obj, do_unlink=True)
                
                # Rename new object to original name
                obj.name = base_name
        
        # Process meshes
        for mesh in imported_data.meshes:
            if not mesh:
                continue
            
            base_name = mesh.name.rsplit('.', 1)[0]
            old_mesh = bpy.data.meshes.get(base_name)
            if old_mesh and old_mesh != mesh:
                # Update references in objects
                for obj in bpy.data.objects:
                    if obj.type == 'MESH' and obj.data == old_mesh:
                        obj.data = mesh
                
                # Remove old mesh
                bpy.data.meshes.remove(old_mesh, do_unlink=True)
                
                # Rename new mesh
                mesh.name = base_name
        
        # Process materials
        for mat in imported_data.materials:
            if not mat:
                continue
            
            base_name = mat.name.rsplit('.', 1)[0]
            old_mat = bpy.data.materials.get(base_name)
            if old_mat and old_mat != mat:
                # Update references
                for obj in bpy.data.objects:
                    if hasattr(obj.data, 'materials'):
                        for i, slot_mat in enumerate(obj.data.materials):
                            if slot_mat == old_mat:
                                obj.data.materials[i] = mat
                
                # Remove old material
                bpy.data.materials.remove(old_mat, do_unlink=True)
                
                # Rename new material
                mat.name = base_name
        
        # Clean up orphaned data blocks
        self._cleanup_orphaned_data()
    
    def _cleanup_orphaned_data(self):
        """Clean up orphaned data blocks after delta replacement"""
        # Clean up meshes with no users
        for mesh in list(bpy.data.meshes):
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh, do_unlink=True)
        
        # Clean up materials with no users
        for mat in list(bpy.data.materials):
            if mat.users == 0 and not mat.use_fake_user:
                bpy.data.materials.remove(mat, do_unlink=True)
        
        # Clean up images with no users
        for img in list(bpy.data.images):
            if img.users == 0 and not img.use_fake_user:
                bpy.data.images.remove(img, do_unlink=True)
        
        # Clean up actions with no users
        for action in list(bpy.data.actions):
            if action.users == 0 and not action.use_fake_user:
                bpy.data.actions.remove(action, do_unlink=True)


def register():
    bpy.utils.register_class(GITBLEND_OT_Checkout)


def unregister():
    bpy.utils.unregister_class(GITBLEND_OT_Checkout)